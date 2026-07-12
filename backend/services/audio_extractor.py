"""
Audio extractor service — Sub-task 3.

Extracts a 16 kHz mono PCM WAV from a video/audio file using FFmpeg.
If the source is already a .wav (or already audio), FFmpeg still runs to
normalise the sample rate and channel count to 16 kHz / mono, which is the
exact format faster-whisper requires.

Audio-only inputs (.mp3) are passed through the same command — FFmpeg handles
both video+audio and audio-only files transparently via the -vn flag (which
is a no-op when there is no video stream).
"""

import subprocess
from pathlib import Path


def extract_audio(input_path: str, output_wav: str) -> None:
    """
    Convert *input_path* to a 16 kHz mono PCM WAV at *output_wav*.

    Works for both video files (extracts audio track) and audio-only files
    (.mp3, .m4a, etc.) — FFmpeg's -vn flag is safe on audio-only inputs.

    Args:
        input_path: Absolute path to the source file.
        output_wav: Absolute path for the output .wav file.

    Raises:
        RuntimeError: If ffmpeg exits with a non-zero return code.
        FileNotFoundError: If ffmpeg is not on PATH.
    """
    cmd = [
        "ffmpeg",
        "-y",                    # overwrite output without prompting
        "-i", input_path,
        "-vn",                   # drop video stream (no-op for audio-only)
        "-acodec", "pcm_s16le",  # 16-bit PCM — required by faster-whisper
        "-ar", "16000",          # 16 kHz sample rate — required by Whisper
        "-ac", "1",              # mono channel
        output_wav,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute hard limit; most files are much faster
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            "ffmpeg not found. Please ensure FFmpeg is installed and on PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg timed out during audio extraction.")

    if result.returncode != 0:
        stderr_snippet = result.stderr.strip()[-500:]  # tail is most relevant
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}) during audio extraction. "
            f"Details: {stderr_snippet}"
        )
