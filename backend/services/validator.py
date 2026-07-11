"""
Validator service — Sub-task 2.

Validates uploaded files by checking:
1. File extension against the allowlist
2. File size against MAX_FILE_SIZE_MB from config
3. Media integrity via ffprobe (duration > 0, parseable format)

This is a pure function module: takes a file path, returns a result dict or
raises ValueError. No HTTP concerns here — the router handles HTTP responses.
"""

import json
import subprocess
from pathlib import Path

import config

ALLOWED_EXTENSIONS = {".mp4", ".mp3", ".mov", ".webm"}

# MIME types that correspond to allowed extensions.
# Used as a secondary sanity check after extension validation.
ALLOWED_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    # Some encoders tag MP3 with these
    "audio/x-mpeg",
    "audio/mpeg3",
}


def validate(filepath: str) -> dict:
    """
    Validate a saved upload file.

    Args:
        filepath: Absolute path to the saved file.

    Returns:
        {"valid": True, "duration_seconds": float}

    Raises:
        ValueError: With a human-readable message on any validation failure.
    """
    path = Path(filepath)

    # 1. Extension check
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(
            f"Unsupported file type '{ext}'. Allowed extensions: {allowed}."
        )

    # 2. File size check — file is already saved, check bytes on disk
    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"Could not read file: {exc}")
    max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        size_mb = size_bytes / (1024 * 1024)
        raise ValueError(
            f"File size {size_mb:.1f} MB exceeds the {config.MAX_FILE_SIZE_MB} MB limit."
        )

    # 3. FFprobe integrity + duration check
    duration = _ffprobe_duration(filepath)
    if duration <= 0:
        raise ValueError(
            "File appears to be corrupted or has zero duration. "
            "Please upload a valid media file."
        )

    return {"valid": True, "duration_seconds": duration}


def _ffprobe_duration(filepath: str) -> float:
    """
    Run ffprobe on the file and return duration in seconds.

    Raises ValueError if ffprobe fails or duration cannot be parsed.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        filepath,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise ValueError(
            "ffprobe not found. Please ensure FFmpeg is installed and on PATH."
        )
    except subprocess.TimeoutExpired:
        raise ValueError("ffprobe timed out while inspecting the file.")

    if result.returncode != 0:
        # ffprobe wrote an error to stderr; include it for debuggability
        stderr_snippet = result.stderr.strip()[:300]
        raise ValueError(
            f"File could not be read by ffprobe — it may be corrupted or "
            f"unsupported. Details: {stderr_snippet}"
        )

    try:
        probe_data = json.loads(result.stdout)
        duration_str = probe_data.get("format", {}).get("duration", "0")
        return float(duration_str)
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        raise ValueError(
            f"Could not parse ffprobe output: {exc}"
        )
