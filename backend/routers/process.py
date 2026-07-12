"""
Process router — Sub-tasks 3 & 4.

POST /process/{job_id}
  - Looks up the uploaded file in TMP_DIR/{job_id}/
  - Creates a background asyncio task that runs the pipeline
  - Returns immediately with {"job_id": ..., "status": "processing"}

Pipeline stages:
  extracting_audio   pct=10
  transcribing       pct=30
  processing_granite pct=60   ← Sub-task 4 addition
  ready              pct=100  (with granite_result payload)

Later sub-tasks (5) will extend the pipeline to add:
  composing_subtitles pct=75
  ready               pct=100  (with full ProcessedResult)
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

import config
from services import audio_extractor, transcriber, granite_processor

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


async def _run_pipeline(app_state, job_id: str) -> None:
    """
    Background task: audio extraction → transcription → Granite processing.

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
            segments = await transcriber.transcribe(audio_wav, str(job_dir))
        except RuntimeError as exc:
            set_error(f"Transcription failed: {exc}")
            return

        # ── 4. Granite processing (pct=60) ────────────────────────────────
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

        # ── 5. Done — mark ready with both whisper segments and granite result
        set_stage(
            "ready",
            100,
            segments=segments,
            granite_result=granite_result,
        )

    except Exception as exc:
        # Catch-all for unexpected errors — never leave job in unknown state
        logger.exception("[%s] Unexpected pipeline error", job_id)
        set_error(f"Unexpected error: {exc}")


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
