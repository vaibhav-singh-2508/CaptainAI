"""
Export router — Sub-tasks 6 & 7.

GET /download/{job_id}/{filename}
  Sub-task 6: Serves any file from the job's tmp directory as a streaming
  response.  Used by the frontend PreviewPlayer to load the original video
  and by ExportButtons to download SRT/TXT/MP4 files.

  Security: filename is validated against a fixed allowlist to prevent
  path traversal attacks.

POST /export/{job_id}
  Sub-task 7: Accepts ExportRequest (segments + style + formats list).
  - Regenerates SRT and TXT from the user-edited segments (using subtitle_data
    schema: id, start, end, text).
  - If "mp4" is requested: calls burner.burn_subtitles() with a force_style
    string built from the user's final StylePreset.
  - Returns download_urls dict: { "srt": "/download/{job_id}/subtitles.srt", ... }

Segment field contract:
  The frontend sends segments as Segment objects (id, start, end, text,
  corrected_text, language).  The `text` field holds the display text that
  the user can edit in the subtitle editor.  The export endpoint uses `text`
  as the subtitle content — this matches subtitle_data.json exactly.

TXT format:
  CaptainAI Transcript

  HH:MM:SS

  <text>

  HH:MM:SS

  <text>
  ...
"""

import asyncio
import logging
import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

import config
from models.schemas import ExportRequest
from services import style_engine, burner

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowlist of filenames that may be downloaded.
# "original.*" is handled with a prefix check below.
_ALLOWED_FILENAME_RE = re.compile(
    r'^(original\.(mp4|mov|webm|mp3|wav|m4a)'
    r'|audio\.wav'
    r'|subtitles\.srt'
    r'|transcript\.txt'
    r'|output\.mp4'
    r'|whisper_segments\.json'
    r'|granite_result\.json)$',
    re.IGNORECASE,
)


def _safe_file_path(job_id: str, filename: str) -> Path:
    """
    Validate job_id and filename, return the absolute Path.

    Raises HTTPException 400 on bad filename.
    Raises HTTPException 404 if the file does not exist.
    """
    # Basic UUID-ish check to prevent path traversal via job_id
    if not re.match(r'^[a-f0-9\-]{8,}$', job_id, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    if not _ALLOWED_FILENAME_RE.match(filename):
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' is not in the list of downloadable files.",
        )

    job_dir = Path(config.TMP_DIR) / job_id
    file_path = job_dir / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found for job '{job_id}'.",
        )

    return file_path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert float seconds to SRT timestamp HH:MM:SS,mmm."""
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seconds_to_txt_timestamp(seconds: float) -> str:
    """Convert float seconds to HH:MM:SS for TXT transcript headers."""
    total_s = int(seconds)
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _write_srt(segments: list, output_path: Path) -> None:
    """
    Write segments to an SRT file.

    Uses segment.text as the display text (the field the user edits in the
    frontend subtitle editor; also the field written in subtitle_data.json).
    """
    lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start_ts = _seconds_to_srt_timestamp(seg.start)
        end_ts   = _seconds_to_srt_timestamp(seg.end)
        lines.append(str(idx))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(seg.text)
        lines.append("")   # mandatory blank line between SRT blocks
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("SRT written: %s (%d subtitles)", output_path, len(segments))


def _write_txt(segments: list, output_path: Path) -> None:
    """
    Write a human-readable transcript to a TXT file.

    Format:
        CaptainAI Transcript

        00:00:00

        Hello everyone.

        00:00:04

        Today we will learn AI.
    """
    lines: list[str] = ["CaptainAI Transcript", ""]
    for seg in segments:
        ts = _seconds_to_txt_timestamp(seg.start)
        lines.append(ts)
        lines.append("")
        lines.append(seg.text)
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("TXT written: %s (%d entries)", output_path, len(segments))


def _find_original_video(job_dir: Path) -> Path | None:
    """Return the path to the original uploaded video file, or None."""
    for ext in (".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a"):
        candidate = job_dir / f"original{ext}"
        if candidate.exists():
            return candidate
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    """
    Serve a job output file for download.

    Used by:
    - PreviewPlayer (original video) — inline streaming
    - ExportButtons (SRT / TXT / MP4 download)
    """
    file_path = _safe_file_path(job_id, filename)

    media_type, _ = mimetypes.guess_type(str(file_path))
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


@router.post("/export/{job_id}")
async def export(job_id: str, request: ExportRequest):
    """
    Export endpoint — Sub-task 7.

    Accepts ExportRequest (segments + style + formats).
    1. Regenerates SRT and TXT from the user's (possibly edited) segments.
    2. If "mp4" is in formats: runs FFmpeg burn-in to produce output.mp4.
    3. Returns download_urls for all requested formats.

    The burn-in uses libx264 re-encoding to permanently embed the subtitles.
    The FFmpeg call runs in a thread pool executor so it does not block the
    async event loop (burn-in can take 10–60+ seconds depending on video length).
    """
    # Validate job_id
    if not re.match(r'^[a-f0-9\-]{8,}$', job_id, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    job_dir = Path(config.TMP_DIR) / job_id
    if not job_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found. Upload a file first.",
        )

    formats = [f.lower() for f in request.formats]
    segments = request.segments
    style    = request.style

    if not segments:
        raise HTTPException(status_code=400, detail="No segments provided.")
    if not formats:
        raise HTTPException(status_code=400, detail="No export formats requested.")

    download_urls: dict[str, str] = {}

    # ── 1. SRT (always regenerated — used for both "srt" download and MP4 burn-in)
    srt_path = job_dir / "subtitles.srt"
    _write_srt(segments, srt_path)
    if "srt" in formats:
        download_urls["srt"] = f"/download/{job_id}/subtitles.srt"

    # ── 2. TXT ───────────────────────────────────────────────────────────────
    if "txt" in formats:
        txt_path = job_dir / "transcript.txt"
        _write_txt(segments, txt_path)
        download_urls["txt"] = f"/download/{job_id}/transcript.txt"

    # ── 3. MP4 burn-in ───────────────────────────────────────────────────────
    if "mp4" in formats:
        original_video = _find_original_video(job_dir)
        if original_video is None:
            raise HTTPException(
                status_code=404,
                detail="Original video file not found for this job. Cannot burn subtitles.",
            )

        output_mp4 = str(job_dir / "output.mp4")
        force_style = style_engine.to_force_style_string(style)

        logger.info(
            "[%s] Starting MP4 burn-in — style=%s force_style=%r",
            job_id, style.preset_name, force_style,
        )

        # Run FFmpeg in a thread executor — it is a blocking subprocess call
        # that can take 10–90 seconds; we must not block the event loop.
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                burner.burn_subtitles,
                str(original_video),
                str(srt_path),
                force_style,
                output_mp4,
            )
        except FileNotFoundError as exc:
            logger.error("[%s] Burn-in file error: %s", job_id, exc)
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("[%s] FFmpeg burn-in failed: %s", job_id, exc)
            raise HTTPException(
                status_code=500,
                detail=f"FFmpeg burn-in failed. {str(exc)[:500]}",
            ) from exc

        download_urls["mp4"] = f"/download/{job_id}/output.mp4"
        logger.info("[%s] MP4 burn-in complete", job_id)

    return JSONResponse(content={"download_urls": download_urls})
