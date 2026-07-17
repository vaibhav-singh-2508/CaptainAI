"""
Subtitle Burner — Sub-task 7.

Provides `burn_subtitles()` which uses FFmpeg to hard-burn an SRT subtitle
file into a video file.  The user's chosen style (font, size, colour, position)
is applied via the FFmpeg `subtitles` filter's `force_style` option.

Design notes:
- The SRT file written by subtitle_composer is the single source of truth for
  timing.  burn_subtitles() does NOT re-time or regenerate subtitles.
- On Windows the subtitles= filter path must use forward slashes (backslashes
  cause FFmpeg to misparse the filter graph string).
- Audio is copied as-is (-c:a copy) — no re-encoding, no quality loss.
- The video stream is re-encoded with libx264 crf=23 (default quality) so that
  the subtitle pixels are permanently written into the output frames.
- FFmpeg stderr is captured and included in RuntimeError messages so debugging
  is straightforward from the API error response.
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def burn_subtitles(
    video_path: str,
    srt_path: str,
    force_style: str,
    output_path: str,
) -> None:
    """
    Burn an SRT subtitle file into *video_path* and write *output_path*.

    Args:
        video_path:   Absolute path to the input video file.
        srt_path:     Absolute path to the SRT file to burn in.
        force_style:  FFmpeg ``force_style`` string (from style_engine).
        output_path:  Absolute path to write the output MP4.

    Raises:
        RuntimeError: If FFmpeg exits with a non-zero return code.
                      The FFmpeg stderr output is included in the message.
        FileNotFoundError: If ``video_path`` or ``srt_path`` do not exist.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if not Path(srt_path).exists():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    # On Windows, forward-slash the path — FFmpeg's subtitles filter uses a
    # colon as part of its filter option syntax (key=value:key=value), so a
    # Windows absolute path like "C:\path\file.srt" causes a parse error.
    # Converting to forward slashes avoids this: "C:/path/file.srt".
    srt_filter_path = srt_path.replace("\\", "/")

    # On Windows, if the path contains a colon (drive letter like "C:/..."),
    # it must be escaped as "C\\:/..." in the filter_complex string.
    if os.name == "nt" and len(srt_filter_path) >= 2 and srt_filter_path[1] == ":":
        # Escape the drive-letter colon: C:/ → C\:/
        srt_filter_path = srt_filter_path[0] + "\\:" + srt_filter_path[2:]

    vf_filter = f"subtitles='{srt_filter_path}':force_style='{force_style}'"

    cmd = [
        "ffmpeg",
        "-y",                   # overwrite output without prompting
        "-i", video_path,       # input video
        "-vf", vf_filter,       # subtitle burn-in filter
        "-c:v", "libx264",      # re-encode video to bake in subtitles
        "-crf", "23",           # quality (lower = better; 23 is FFmpeg default)
        "-preset", "fast",      # encoding speed/compression tradeoff
        "-c:a", "copy",         # copy audio track as-is
        output_path,
    ]

    logger.info(
        "FFmpeg burn-in starting: output=%s style=%r",
        output_path, force_style,
    )
    logger.debug("FFmpeg command: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        stderr_snippet = result.stderr[-2000:] if result.stderr else "(no stderr)"
        logger.error("FFmpeg burn-in failed (rc=%d):\n%s", result.returncode, stderr_snippet)
        raise RuntimeError(
            f"FFmpeg burn-in failed (exit code {result.returncode}). "
            f"FFmpeg stderr: {stderr_snippet}"
        )

    logger.info("FFmpeg burn-in complete: %s", output_path)
