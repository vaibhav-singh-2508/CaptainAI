"""
Export router — Sub-tasks 6 & 7.

GET /download/{job_id}/{filename}
  Sub-task 6: Serves any file from the job's tmp directory as a streaming
  response.  Used by the frontend PreviewPlayer to load the original video
  and will be used by ExportButtons to download SRT/TXT/MP4 files.

  Security: filename is validated against a fixed allowlist to prevent
  path traversal attacks.

POST /export/{job_id}
  Sub-task 7 (stub): Accepts ExportRequest and returns 501 until implemented.
"""

import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

import config

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


@router.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    """
    Serve a job output file for download.

    Used by:
    - PreviewPlayer (original video) — inline streaming
    - ExportButtons (SRT / TXT download)
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
async def export(job_id: str):
    """
    Export endpoint — Sub-task 7.

    Accepts ExportRequest (segments + style + formats), regenerates SRT/TXT,
    optionally runs FFmpeg burn-in for MP4, returns download_urls dict.

    Not yet implemented in Sub-task 6.
    """
    return JSONResponse(status_code=501, content={"detail": "Export (FFmpeg burn-in) will be implemented in Sub-task 7."})
