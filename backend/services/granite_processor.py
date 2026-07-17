"""
Granite Processor — Sub-task 4.

Sends the raw Whisper transcript to a locally-hosted IBM Granite model
(granite3.3:2b via Ollama) and returns structured metadata.

Design notes:
- Uses Ollama's /api/chat endpoint with `"format": "json"` to *enforce* valid
  structured output at the API level — not just a prompt instruction.
- A single call per job returns ALL metadata: corrected segments, language
  profile, genre, keywords, style preset, and summary.
- Granite corrects text only.  Timestamps are Whisper's source of truth and
  are NEVER passed to Granite nor expected back from it.
- The "confidence" field in `genre` is the model's own self-reported estimate,
  not a statistically calibrated probability.  It should be interpreted as a
  soft indicator of certainty, not a precise score.
- On any failure (Ollama unreachable, non-JSON response, schema mismatch),
  the processor returns a fallback result built from raw Whisper segments so
  the pipeline never silently crashes.
"""

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)

# ── Prompt constants ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a subtitle intelligence assistant. "
    "You must respond with valid JSON only. "
    "Do not include any explanation, markdown, or code fences."
)

_USER_PROMPT_TEMPLATE = """\
You are processing video subtitle segments. Return a JSON object with these 6 keys.
CRITICAL: NEVER translate any word from one language to another. If the speaker said a word in Hindi, keep it in Hindi (in Latin/Roman script as transcribed). If they said a word in English, keep it in English. Your ONLY job is fixing grammar, spelling, and removing filler words — you must NOT change the language of any word. Preserve the exact language mix exactly as spoken.

INPUT SEGMENTS:
{segments_json}

REQUIRED OUTPUT (JSON object, all 6 keys mandatory):
1. "corrected_segments" - array with one entry per input segment (ALL IDs, same order):
   [{{"id": 1, "corrected_text": "fixed text"}}, {{"id": 2, "corrected_text": "fixed text"}}, ...]
   Fix grammar, remove filler words (um, uh, like, you know). Keep meaning unchanged.
   For Hinglish (mixed Hindi+English): keep the natural mix, do NOT force a single language.

2. "language_profile" - one object describing the content globally:
   {{"primary_language": "en"|"hi"|"hi-en", "secondary_language": null, "contains_code_switching": true|false}}
   Set contains_code_switching to true for any Hindi+English mixing (Hinglish).

3. "genre" - classification object:
   {{"label": "study"|"talk"|"song"|"vlog", "confidence": 0.95}}

4. "keywords" - array of 5-8 topic strings extracted from the content.

5. "style_preset" - one of: "cinematic", "social", "education", "minimal"

6. "summary" - one sentence about the video content.

IMPORTANT: corrected_segments MUST contain one entry for EVERY segment ID in the input.
"""


# ── Ollama client ─────────────────────────────────────────────────────────────

def _call_ollama(prompt_segments_json: str) -> dict:
    """
    POST to Ollama /api/chat with format:"json" enforcement.

    Returns the parsed JSON dict from Granite's response.

    Raises:
        RuntimeError: if Ollama is unreachable or returns a non-200 status.
        json.JSONDecodeError: if the response body is not valid JSON.
    """
    payload = {
        "model": config.OLLAMA_MODEL,
        "format": "json",   # Ollama-level JSON enforcement — not just a prompt hint
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_PROMPT_TEMPLATE.format(
                    segments_json=prompt_segments_json
                ),
            },
        ],
    }

    # ensure_ascii=True for the request body — UTF-8 encode handles the rest
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=f"{config.OLLAMA_URL.rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama unreachable at {config.OLLAMA_URL}: {exc}"
        ) from exc

    envelope = json.loads(raw)  # outer Ollama envelope
    content = envelope["message"]["content"]
    result = json.loads(content)  # the model's structured JSON payload
    if not isinstance(result, dict):
        raise ValueError(f"Ollama response content is not a JSON object: {type(result)}")
    return result


# ── Fallback builder ──────────────────────────────────────────────────────────

def _build_fallback(segments: list[dict], reason: str) -> dict:
    """
    Build a minimal valid GraniteResult using raw Whisper text.

    Used when Ollama fails or returns unparseable output.  The pipeline
    still completes; downstream stages get raw text + default style.
    """
    logger.warning("Granite fallback activated: %s", reason)
    return {
        "corrected_segments": [
            {"id": seg["id"], "corrected_text": seg["text"]}
            for seg in segments
        ],
        "language_profile": {
            "primary_language": "en",
            "secondary_language": None,
            "contains_code_switching": False,
        },
        "genre": {"label": "talk", "confidence": 0.0},
        "keywords": [],
        "style_preset": "minimal",
        "summary": "Transcript processed without AI analysis (Granite unavailable).",
        "_fallback": True,
        "_fallback_reason": reason,
    }


# ── Schema validator ──────────────────────────────────────────────────────────

_VALID_GENRE_LABELS = {"study", "talk", "song", "vlog"}
_VALID_STYLE_PRESETS = {"cinematic", "social", "education", "minimal"}


def _validate_and_normalise(data: Any, segment_ids: set[int], segments: list[dict]) -> dict:
    """
    Validate the parsed Granite response against the expected schema.

    Raises ValueError with a descriptive message on any structural mismatch.
    This keeps _call_ollama clean and makes fallback logic easy to trigger.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

    # Granite (2b) sometimes returns flattened "genre.label" / "genre.confidence"
    # keys instead of a nested "genre" object.  Normalise before validation.
    if "genre.label" in data or "genre.confidence" in data:
        data["genre"] = {
            "label": data.pop("genre.label", "talk"),
            "confidence": data.pop("genre.confidence", 0.5),
        }

    for required_key in (
        "corrected_segments", "language_profile", "genre",
        "keywords", "style_preset", "summary",
    ):
        if required_key not in data:
            raise ValueError(f"Missing required key: '{required_key}'")

    # corrected_segments
    corrected = data["corrected_segments"]
    if not isinstance(corrected, list):
        raise ValueError("'corrected_segments' must be a list")
    returned_ids = set()
    for item in corrected:
        if not isinstance(item, dict) or "id" not in item or "corrected_text" not in item:
            raise ValueError(f"Invalid corrected_segment entry: {item!r}")
        returned_ids.add(int(item["id"]))

    # Fill gaps with raw Whisper text so no segment is ever dropped downstream
    missing = segment_ids - returned_ids
    if missing:
        logger.warning("Granite did not return corrected_text for segment IDs: %s", missing)
        segment_lookup = {seg["id"]: seg["text"] for seg in segments}
        for missing_id in missing:
            corrected.append({
                "id": missing_id,
                "corrected_text": segment_lookup[missing_id],
            })
        data["corrected_segments"] = corrected

    # language_profile
    lp = data["language_profile"]
    if not isinstance(lp, dict):
        raise ValueError("'language_profile' must be an object")
    for lp_key in ("primary_language", "contains_code_switching"):
        if lp_key not in lp:
            raise ValueError(f"'language_profile' missing key: '{lp_key}'")

    # genre
    genre = data["genre"]
    if not isinstance(genre, dict):
        raise ValueError("'genre' must be an object")

    # Granite (2b) sometimes confuses style preset names with genre labels.
    # Map the known style names back to valid genre labels.
    _STYLE_TO_GENRE = {
        "education": "study",
        "cinematic": "song",
        "social":    "vlog",
        "minimal":   "talk",
    }
    raw_label = genre.get("label", "")
    if raw_label not in _VALID_GENRE_LABELS:
        remapped = _STYLE_TO_GENRE.get(raw_label)
        if remapped:
            logger.debug(
                "Remapping genre label '%s' → '%s' (style/genre confusion)", raw_label, remapped
            )
            genre["label"] = remapped
        else:
            raise ValueError(
                f"'genre.label' must be one of {_VALID_GENRE_LABELS}, "
                f"got {raw_label!r}"
            )

    # Clamp confidence to [0.0, 1.0]; default to 0.5 if missing
    try:
        conf = genre.get("confidence")
        genre["confidence"] = max(0.0, min(1.0, float(conf))) if conf is not None else 0.5
    except (TypeError, ValueError):
        genre["confidence"] = 0.5

    # style_preset
    if data["style_preset"] not in _VALID_STYLE_PRESETS:
        raise ValueError(
            f"'style_preset' must be one of {_VALID_STYLE_PRESETS}, "
            f"got {data['style_preset']!r}"
        )

    return data

# ── Public API ────────────────────────────────────────────────────────────────

async def process(segments: list[dict], job_dir: str) -> dict:
    """
    Send *segments* to Granite and return the structured result dict.

    The result is also persisted to ``{job_dir}/granite_result.json``.

    Args:
        segments: Raw Whisper segment dicts (id, start, end, text).
        job_dir:  Path to the job directory.

    Returns:
        A dict matching the GraniteResult schema.  On failure, a fallback
        dict is returned (never raises).
    """
    segment_ids = {seg["id"] for seg in segments}

    # Only id + text go to Granite — timestamps stay with Whisper
    prompt_segments = [
        {"id": seg["id"], "text": seg["text"]}
        for seg in segments
    ]
    # ensure_ascii=False preserves Hindi/Unicode text in the prompt body.
    # The HTTP layer encodes the full request as UTF-8 bytes.
    prompt_segments_json = json.dumps(prompt_segments, ensure_ascii=False, indent=2)

    result: dict
    try:
        logger.info(
            "Calling Granite (%s) via Ollama at %s — %d segments",
            config.OLLAMA_MODEL, config.OLLAMA_URL, len(segments),
        )
        raw_result = _call_ollama(prompt_segments_json)
        result = _validate_and_normalise(raw_result, segment_ids, segments)
        logger.info(
            "Granite response OK — genre=%s confidence=%.2f style=%s "
            "code_switching=%s keywords=%d",
            result["genre"]["label"],
            result["genre"]["confidence"],
            result["style_preset"],
            result["language_profile"].get("contains_code_switching"),
            len(result.get("keywords", [])),
        )
    except RuntimeError as exc:
        reason = exc.args[0].encode("ascii", errors="replace").decode("ascii") if exc.args else str(type(exc))
        result = _build_fallback(segments, f"Ollama error: {reason}")
    except json.JSONDecodeError as exc:
        result = _build_fallback(segments, f"JSON parse error: {exc.msg} (line {exc.lineno})")
    except ValueError as exc:
        reason = str(exc).encode("ascii", errors="replace").decode("ascii")
        result = _build_fallback(segments, f"Schema validation error: {reason}")
    except Exception as exc:
        logger.exception("Unexpected error in Granite processor")
        reason = repr(exc).encode("ascii", errors="replace").decode("ascii")
        result = _build_fallback(segments, f"Unexpected error: {reason}")

    # Save to disk
    out_path = Path(job_dir) / "granite_result.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Granite result saved to %s", out_path)

    return result
