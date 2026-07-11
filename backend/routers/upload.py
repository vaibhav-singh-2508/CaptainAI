"""
Upload router — Sub-task 2.

POST /upload
  - Accepts multipart/form-data with a 'file' field.
  - Validates extension, size, and media integrity (ffprobe).
  - Saves to TMP_DIR/{job_id}/original.{ext}.
  - Returns { job_id, filename, duration_seconds }.
"""

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

import config
from services import validator

router = APIRouter()

# Read chunk size for streaming the upload to disk (1 MB chunks).
_CHUNK_SIZE = 1024 * 1024


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a media file (MP4, MP3, MOV, WEBM).

    Returns:
        200: { "job_id": str, "filename": str, "duration_seconds": float }
        422: Validation error (bad extension, oversized, corrupted, etc.)
    """
    # --- Derive and validate extension early (before writing to disk) ---
    original_filename = file.filename or ""
    ext = Path(original_filename).suffix.lower()

    if ext not in validator.ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(validator.ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed extensions: {allowed}.",
        )

    # --- Create job directory ---
    job_id = str(uuid.uuid4())
    job_dir = Path(config.TMP_DIR) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    save_path = job_dir / f"original{ext}"

    # --- Stream file to disk and track size ---
    size_bytes = 0
    max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024

    try:
        async with aiofiles.open(save_path, "wb") as out:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    # Exceeded limit — clean up and reject immediately
                    await out.close()
                    save_path.unlink(missing_ok=True)
                    job_dir.rmdir()
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"File size exceeds the {config.MAX_FILE_SIZE_MB} MB limit. "
                            f"Please upload a smaller file."
                        ),
                    )
                await out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        # Clean up on unexpected write failure
        save_path.unlink(missing_ok=True)
        try:
            job_dir.rmdir()
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    # --- Validate saved file with ffprobe ---
    try:
        result = validator.validate(str(save_path))
    except ValueError as exc:
        # Clean up rejected file
        save_path.unlink(missing_ok=True)
        try:
            job_dir.rmdir()
        except OSError:
            pass
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "job_id": job_id,
        "filename": original_filename,
        "duration_seconds": result["duration_seconds"],
    }
