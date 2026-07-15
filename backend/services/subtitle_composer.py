"""
Subtitle Composer — Sub-task 5.

Merges Whisper timestamps with Granite corrected text and produces three
output artefacts in the job directory:

  subtitle_data.json  — the unified subtitle structure (source of truth)
  subtitles.srt       — standard SRT file, UTF-8
  transcript.txt      — plain text transcript, UTF-8

Design decisions:
- Whisper timestamps are never modified.  The merge is strictly:
    subtitle.start = whisper_segment.start
    subtitle.end   = whisper_segment.end
    subtitle.text  = granite corrected_text  (or whisper text if not present)
- Segment order follows Whisper ID order (ascending).
- SRT index starts at 1.
- SRT timestamp separator uses comma (,), not period — the standard requires
  "HH:MM:SS,mmm".  A period here is the most common SRT formatting mistake.
- All output files are written as UTF-8 with explicit encoding= to avoid
  Windows cp1252 codec errors on non-ASCII content (Hinglish, etc.).
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Timestamp formatter ───────────────────────────────────────────────────────

def _seconds_to_srt_timestamp(seconds: float) -> str:
    """
    Convert a float seconds value to SRT timestamp format: HH:MM:SS,mmm

    The comma separator is mandatory per the SRT specification.
    A period (.) is invalid and will cause most players to reject the file.

    Examples:
        0.0       → "00:00:00,000"
        3.5       → "00:00:03,500"
        90.123    → "00:01:30,123"
        3661.007  → "01:01:01,007"
    """
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── Core merge function ───────────────────────────────────────────────────────

def compose(
    whisper_segments: list[dict],
    granite_result: dict,
    job_dir: str,
) -> list[dict]:
    """
    Merge Whisper timestamps with Granite corrected text.

    Saves ``subtitle_data.json``, ``subtitles.srt``, and ``transcript.txt``
    to *job_dir*.

    Args:
        whisper_segments: List of dicts from whisper_segments.json.
                          Each has: id, start, end, text.
        granite_result:   Dict from granite_result.json.
                          Has corrected_segments list with id + corrected_text.
        job_dir:          Path string to the job directory.

    Returns:
        The unified subtitle list (same content as subtitle_data.json).
    """
    job_path = Path(job_dir)

    # Build a lookup from segment id → corrected_text
    corrected_lookup: dict[int, str] = {}
    for item in granite_result.get("corrected_segments", []):
        seg_id = int(item["id"])
        corrected_lookup[seg_id] = item["corrected_text"]

    # Merge: Whisper timestamps + Granite text (fallback to Whisper text)
    subtitles: list[dict] = []
    for seg in sorted(whisper_segments, key=lambda s: s["id"]):
        seg_id = int(seg["id"])
        if seg_id in corrected_lookup:
            text = corrected_lookup[seg_id]
        else:
            # Granite did not return a correction for this segment — use raw
            logger.debug(
                "No Granite correction for segment %d — using raw Whisper text", seg_id
            )
            text = seg["text"]

        subtitles.append({
            "id": seg_id,
            "start": seg["start"],   # Whisper timestamp — never modified
            "end": seg["end"],       # Whisper timestamp — never modified
            "text": text,
        })

    # ── Write subtitle_data.json ──────────────────────────────────────────────
    subtitle_data_path = job_path / "subtitle_data.json"
    subtitle_data_path.write_text(
        json.dumps(subtitles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "subtitle_data.json saved — %d subtitle(s) at %s",
        len(subtitles), subtitle_data_path,
    )

    # ── Write subtitles.srt ───────────────────────────────────────────────────
    srt_path = job_path / "subtitles.srt"
    _write_srt(subtitles, srt_path)
    logger.info("subtitles.srt saved at %s", srt_path)

    # ── Write transcript.txt ──────────────────────────────────────────────────
    txt_path = job_path / "transcript.txt"
    _write_txt(subtitles, txt_path)
    logger.info("transcript.txt saved at %s", txt_path)

    return subtitles


# ── SRT writer ────────────────────────────────────────────────────────────────

def _write_srt(subtitles: list[dict], output_path: Path) -> None:
    """
    Write *subtitles* to *output_path* in valid SRT format (UTF-8).

    SRT block format:
        <index>
        <HH:MM:SS,mmm> --> <HH:MM:SS,mmm>
        <text>
        <blank line>

    Index starts at 1. The blank line after each block is mandatory per spec.
    """
    lines: list[str] = []
    for srt_index, sub in enumerate(subtitles, start=1):
        start_ts = _seconds_to_srt_timestamp(sub["start"])
        end_ts   = _seconds_to_srt_timestamp(sub["end"])
        lines.append(str(srt_index))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(sub["text"])
        lines.append("")  # mandatory blank line between blocks

    output_path.write_text("\n".join(lines), encoding="utf-8")


# ── TXT writer ────────────────────────────────────────────────────────────────

def _write_txt(subtitles: list[dict], output_path: Path) -> None:
    """
    Write the plain transcript (text only, no timestamps) to *output_path*.

    Each subtitle's text is on its own line, joined by newlines.
    """
    transcript = "\n".join(sub["text"] for sub in subtitles)
    output_path.write_text(transcript, encoding="utf-8")


# ── Save-only helper (used after translation) ─────────────────────────────────

def save_subtitles(subtitles: list[dict], job_dir: str) -> None:
    """
    Persist *subtitles* to ``subtitle_data.json``, ``subtitles.srt``, and
    ``transcript.txt`` in *job_dir*.

    Called after Hindi→English translation to overwrite the original-language
    files with the translated versions.  The subtitle structure must match the
    format produced by ``compose()`` (id, start, end, text keys).
    """
    job_path = Path(job_dir)

    subtitle_data_path = job_path / "subtitle_data.json"
    subtitle_data_path.write_text(
        json.dumps(subtitles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_srt(subtitles, job_path / "subtitles.srt")
    _write_txt(subtitles, job_path / "transcript.txt")
    logger.info(
        "save_subtitles: overwrote subtitle files with %d translated subtitle(s)",
        len(subtitles),
    )


# ── File-based entry point (loads from disk) ──────────────────────────────────

def compose_from_job_dir(job_dir: str) -> list[dict]:
    """
    Load whisper_segments.json and granite_result.json from *job_dir*,
    then run compose().

    Useful for re-running composition without re-running the full pipeline,
    and for testing.

    Raises:
        FileNotFoundError: if either input JSON file is missing.
        json.JSONDecodeError: if either file contains invalid JSON.
    """
    job_path = Path(job_dir)

    whisper_path = job_path / "whisper_segments.json"
    granite_path = job_path / "granite_result.json"

    if not whisper_path.exists():
        raise FileNotFoundError(f"whisper_segments.json not found in {job_dir}")
    if not granite_path.exists():
        raise FileNotFoundError(f"granite_result.json not found in {job_dir}")

    whisper_segments = json.loads(whisper_path.read_text(encoding="utf-8"))
    granite_result   = json.loads(granite_path.read_text(encoding="utf-8"))

    return compose(whisper_segments, granite_result, job_dir)
