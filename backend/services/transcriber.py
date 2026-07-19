"""
Transcriber service — Sub-task 3.

Wraps faster-whisper for audio transcription.

Key design points (from the plan):
- WhisperModel is loaded ONCE at app startup and shared across all requests.
  The model handle is injected via `set_model()` called from main.py lifespan.
- language=None forces auto-detection — critical for Hinglish / code-switching.
- compute_type="float16" on CUDA; falls back to "int8" on CPU (float16 is
  invalid on CPU builds of ctranslate2).
- Transcription runs in a ThreadPoolExecutor so it does not block the asyncio
  event loop, allowing SSE streams to continue emitting during transcription.
- word_timestamps=False — segment-level is sufficient; word timestamps are a
  stretch feature left for later.
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level model handle — set once at startup via set_model()
_model = None

# Single shared executor for blocking transcription calls
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")


def set_model(model) -> None:
    """Store the loaded WhisperModel instance for use by transcribe()."""
    global _model
    _model = model


def get_model():
    """Return the loaded WhisperModel, or None if not yet initialised."""
    return _model


def _transcribe_sync(audio_path: str, language: str | None = None) -> list[dict]:
    """
    Blocking transcription call — runs inside a thread executor.

    Args:
        audio_path: Path to the 16 kHz mono WAV file.
        language:   ISO 639-1 language code to force ("en", "hi"), or None for
                    auto-detection.  Auto-detection is the default and is
                    required for Hinglish / code-switched content.

    Returns a list of segment dicts: [{"id": int, "start": float,
    "end": float, "text": str}, ...]
    """
    if _model is None:
        raise RuntimeError("Whisper model has not been loaded. Check app startup.")

    logger.info(
        "[LANG-DIAG] Whisper called with: language=%r task=transcribe",
        language,
    )

    segments_iter, info = _model.transcribe(
        audio_path,
        language=language,      # None = auto-detect; "en"/"hi" = forced
        task="transcribe",
        word_timestamps=False,  # segment-level only
        beam_size=5,
    )

    detected_lang = info.language
    logger.info(
        "[LANG-DIAG] Whisper detected language: %s (probability %.2f)",
        detected_lang,
        info.language_probability,
    )

    segments = []
    for seg in segments_iter:   # iterator — consume fully
        segments.append({
            "id": seg.id,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
        })

    return segments


async def transcribe(
    audio_path: str,
    job_dir: str,
    language: str | None = None,
) -> list[dict]:
    """
    Transcribe *audio_path* asynchronously (non-blocking to the event loop).

    Saves results to ``{job_dir}/whisper_segments.json``.

    Args:
        audio_path: Path to the 16 kHz mono WAV file.
        job_dir:    Path to the job directory where JSON will be saved.
        language:   ISO 639-1 code ("en", "hi") to force, or None for
                    auto-detection (default).

    Returns:
        List of segment dicts with id, start, end, text.

    Raises:
        RuntimeError: If transcription fails or the model is not loaded.
    """
    loop = asyncio.get_event_loop()
    segments = await loop.run_in_executor(
        _executor,
        _transcribe_sync,
        audio_path,
        language,
    )

    # Persist raw Whisper output to disk
    out_path = Path(job_dir) / "whisper_segments.json"
    out_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Whisper segments saved to %s (%d segments)", out_path, len(segments))

    return segments
