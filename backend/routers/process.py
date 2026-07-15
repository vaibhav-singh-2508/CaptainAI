"""
Process router — Sub-tasks 3, 4, 5 + Language Selection feature.

POST /process/{job_id}
  - Looks up the uploaded file in TMP_DIR/{job_id}/
  - Reads job_config.json for spoken_language / subtitle_output preferences
  - Creates a background asyncio task that runs the pipeline
  - Returns immediately with {"job_id": ..., "status": "processing"}

Pipeline stages:
  extracting_audio    pct=10
  transcribing        pct=30
  processing_granite  pct=60
  composing_subtitles pct=75
  translating         pct=88  ← only when subtitle_output="en" + Hindi detected
  ready               pct=100 (with subtitles + granite_result payload)

Language behaviour:
  spoken_language="auto"  → Whisper auto-detects (language=None)
  spoken_language="en"    → Whisper forced to English
  spoken_language="hi"    → Whisper forced to Hindi

  subtitle_output="original" → subtitles in the spoken language (no translation)
  subtitle_output="en"       → translate Hindi subtitles to English
                               (only runs if spoken language is Hindi)

AI Analysis (genre, keywords, summary) ALWAYS operates on the ORIGINAL
transcript — never on translated subtitles.
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

import config
from services import audio_extractor, transcriber, granite_processor, subtitle_composer, translator

logger = logging.getLogger(__name__)

router = APIRouter()

# Audio extensions that skip video-track extraction but still go through
# FFmpeg for sample-rate / channel normalisation.
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


def _find_original(job_dir: Path) -> Path:
    """Return the uploaded original file path inside job_dir."""
    for ext in (".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a"):
        candidate = job_dir / f"original{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No recognised original file found in job directory {job_dir}"
    )


def _load_job_config(job_dir: Path) -> dict:
    """
    Load job_config.json from *job_dir*.

    Returns defaults if the file is missing (e.g. jobs created before the
    language-selection feature was added).
    """
    config_path = job_dir / "job_config.json"
    defaults = {"spoken_language": "auto", "subtitle_output": "original"}
    if not config_path.exists():
        return defaults
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return {**defaults, **data}
    except Exception:
        logger.warning("Could not read job_config.json — using defaults")
        return defaults


def _whisper_language(spoken_language: str) -> str | None:
    """
    Convert the UI spoken_language value to a Whisper language code.

    "auto" → None  (Whisper auto-detects)
    "en"   → "en"
    "hi"   → "hi"
    """
    if spoken_language == "auto":
        return None
    return spoken_language


async def _run_pipeline(app_state, job_id: str) -> None:
    """
    Background task: audio extraction → transcription → Granite → subtitles
    → optional translation.

    Updates app_state.jobs[job_id] at each stage so the SSE stream can
    report live progress.
    """
    job_dir = Path(config.TMP_DIR) / job_id
    jobs = app_state.jobs

    def set_stage(stage: str, pct: int, **extra):
        jobs[job_id] = {"stage": stage, "pct": pct, "error": None, **extra}
        logger.info("[%s] stage=%s pct=%d", job_id, stage, pct)

    def set_error(message: str):
        jobs[job_id] = {"stage": "error", "pct": 0, "error": message}
        logger.error("[%s] pipeline error: %s", job_id, message)

    try:
        # ── 0. Load job language config ───────────────────────────────────
        job_cfg = _load_job_config(job_dir)
        spoken_language: str = job_cfg["spoken_language"]
        subtitle_output: str = job_cfg["subtitle_output"]
        whisper_lang = _whisper_language(spoken_language)

        logger.info(
            "[%s] language config: spoken_language=%s subtitle_output=%s",
            job_id, spoken_language, subtitle_output,
        )

        # ── 1. Locate the uploaded file ───────────────────────────────────
        try:
            original_path = _find_original(job_dir)
        except FileNotFoundError as exc:
            set_error(str(exc))
            return

        # ── 2. Audio extraction (pct=10) ──────────────────────────────────
        set_stage("extracting_audio", 10)

        audio_wav = str(job_dir / "audio.wav")

        # Run blocking FFmpeg call in a thread so the event loop stays free
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,  # default ThreadPoolExecutor
                audio_extractor.extract_audio,
                str(original_path),
                audio_wav,
            )
        except (RuntimeError, FileNotFoundError) as exc:
            set_error(f"Audio extraction failed: {exc}")
            return

        # ── 3. Transcription (pct=30) ─────────────────────────────────────
        set_stage("transcribing", 30)

        try:
            # Pass whisper_lang so the user's spoken language choice is respected.
            # None = auto-detect (default); "en"/"hi" = forced language.
            segments = await transcriber.transcribe(
                audio_wav, str(job_dir), language=whisper_lang
            )
        except RuntimeError as exc:
            set_error(f"Transcription failed: {exc}")
            return

        # ── 4. Granite processing (pct=60) ────────────────────────────────
        # IMPORTANT: Granite ALWAYS operates on the raw Whisper segments
        # (original transcript). It must NEVER receive translated text.
        set_stage("processing_granite", 60)

        # granite_processor.process() never raises — returns fallback on error.
        # The Ollama call is a blocking HTTP request; run it in the executor
        # so the event loop (and SSE streams) remain responsive.
        granite_result = await loop.run_in_executor(
            None,
            _run_granite_sync,
            segments,
            str(job_dir),
        )

        # ── 5. Subtitle composition (pct=75) ──────────────────────────────
        # Compose subtitles from the ORIGINAL corrected segments first.
        # Translation (if requested) happens AFTER composition.
        set_stage("composing_subtitles", 75)

        try:
            subtitles = subtitle_composer.compose(
                segments, granite_result, str(job_dir)
            )
        except Exception as exc:
            set_error(f"Subtitle composition failed: {exc}")
            return

        # ── 6. Optional: Hindi → English translation (pct=88) ─────────────
        # Determine the actual spoken language.  When spoken_language="auto",
        # Whisper will have detected the language — check what it found in
        # the granite result's language_profile.
        actual_language = _resolve_actual_language(
            spoken_language, granite_result
        )
        should_translate = (
            subtitle_output == "en"
            and actual_language == "hi"
        )

        if should_translate:
            set_stage("translating", 88)
            logger.info(
                "[%s] Translating subtitles Hindi → English (%d segments)",
                job_id, len(subtitles),
            )
            subtitles = await loop.run_in_executor(
                None,
                translator.translate_segments_to_english,
                subtitles,
            )
            # Persist the translated subtitles (overwrite the Hindi versions)
            try:
                subtitle_composer.save_subtitles(subtitles, str(job_dir))
            except Exception as exc:
                logger.warning("[%s] Could not persist translated subtitles: %s", job_id, exc)
        elif subtitle_output == "en" and actual_language != "hi":
            # User asked for English output but the video is already English
            # (or undetected). No translation needed — log for clarity.
            logger.info(
                "[%s] subtitle_output=en but actual_language=%s — no translation needed",
                job_id, actual_language,
            )

        # ── 7. Done — ready with all artefacts ────────────────────────────
        set_stage(
            "ready",
            100,
            subtitles=subtitles,
            granite_result=granite_result,
        )

    except Exception as exc:
        # Catch-all for unexpected errors — never leave job in unknown state
        logger.exception("[%s] Unexpected pipeline error", job_id)
        set_error(f"Unexpected error: {exc}")


def _resolve_actual_language(spoken_language: str, granite_result: dict) -> str:
    """
    Determine the actual spoken language for translation decision logic.

    When spoken_language="auto", we rely on the language_profile returned by
    Granite (which in turn reflects what Whisper detected).  When the user
    explicitly chose "en" or "hi", we use that directly.

    Returns an ISO 639-1 code string ("en", "hi", "hi-en", etc.) or "unknown".
    """
    if spoken_language in ("en", "hi"):
        return spoken_language

    # Auto-detect path: read from Granite's language_profile
    try:
        primary = granite_result["language_profile"]["primary_language"]
        return primary  # e.g. "en", "hi", "hi-en"
    except (KeyError, TypeError):
        return "unknown"


def _run_granite_sync(segments: list[dict], job_dir: str) -> dict:
    """
    Synchronous wrapper around the async granite_processor.process().

    Used to run the Granite call inside run_in_executor() while keeping
    granite_processor.process() as an async function for direct use in
    async contexts (e.g. tests, Sub-task 5 integration).
    """
    import asyncio as _asyncio
    return _asyncio.run(granite_processor.process(segments, job_dir))


@router.post("/process/{job_id}")
async def process_job(job_id: str, request: Request):
    """
    Start the processing pipeline for *job_id*.

    Returns immediately; progress is streamed via GET /status/{job_id}.
    """
    job_dir = Path(config.TMP_DIR) / job_id
    if not job_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found. Upload a file first.",
        )

    # Prevent double-processing
    existing = request.app.state.jobs.get(job_id)
    if existing and existing.get("stage") not in (None, "error"):
        raise HTTPException(
            status_code=409,
            detail=f"Job '{job_id}' is already being processed (stage: {existing['stage']}).",
        )

    # Seed the job state immediately so SSE can start streaming at once
    request.app.state.jobs[job_id] = {"stage": "queued", "pct": 0, "error": None}

    # Fire-and-forget background task — does NOT block this response
    asyncio.create_task(
        _run_pipeline(request.app.state, job_id),
        name=f"pipeline-{job_id}",
    )

    return {"job_id": job_id, "status": "processing"}
