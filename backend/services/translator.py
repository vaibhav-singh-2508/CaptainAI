"""
Translator service — Language Selection feature.

Provides Hindi → English subtitle translation using the local Granite model
via Ollama.  Translation is ONLY performed when the user explicitly requests
English output AND the spoken language is detected/known to be Hindi.

Design principles:
- CaptainAI NEVER automatically translates. Translation only runs when
  subtitle_output == "en" AND spoken language is Hindi.
- AI Analysis (genre, keywords, summary) ALWAYS operates on the ORIGINAL
  transcript — never on translated subtitles.
- If translation fails for any segment, the original Hindi text is preserved
  (graceful degradation — never silently drop content).
- Segments are translated in a single batched Ollama call to minimise
  round-trip cost while keeping context coherent across segments.

TODO: Future Enhancement:
Support Hinglish transcription and subtitle generation while preserving
mixed-language speech and allowing optional translation.
"""

import json
import logging
import urllib.error
import urllib.request

import config

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a professional subtitle translator. "
    "You must respond with valid JSON only. "
    "Do not include any explanation, markdown, or code fences."
)

_USER_PROMPT_TEMPLATE = """\
Translate the following Hindi subtitle segments into natural, fluent English.
Return a JSON object with a single key "translated_segments" containing an array.
Each entry must have "id" (integer, same as input) and "text" (the English translation).

Rules:
- Preserve the meaning faithfully. Do not paraphrase.
- Keep proper nouns, names, and technical terms unchanged.
- Keep each translation concise — subtitles must be readable on screen.
- If a segment is already in English, copy it unchanged.
- Every input id must appear in the output. Do not skip any segment.

Segments to translate:
{segments_json}
"""


# ── Ollama client ─────────────────────────────────────────────────────────────

def _call_ollama_translate(segments_json: str) -> dict:
    """
    POST to Ollama /api/chat to translate segments.

    Returns parsed JSON dict from the model response.

    Raises:
        RuntimeError: if Ollama is unreachable or returns non-200.
        json.JSONDecodeError: if response is not valid JSON.
    """
    payload = {
        "model": config.OLLAMA_MODEL,
        "format": "json",
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_PROMPT_TEMPLATE.format(
                    segments_json=segments_json
                ),
            },
        ],
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=f"{config.OLLAMA_URL.rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama unreachable at {config.OLLAMA_URL}: {exc}"
        ) from exc

    envelope = json.loads(raw)
    content = envelope["message"]["content"]
    result = json.loads(content)
    if not isinstance(result, dict):
        raise ValueError(
            f"Translation response is not a JSON object: {type(result)}"
        )
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def translate_segments_to_english(subtitles: list[dict]) -> list[dict]:
    """
    Translate Hindi subtitle segments to English using Granite via Ollama.

    This function is SYNCHRONOUS — call it from run_in_executor() to avoid
    blocking the asyncio event loop.

    IMPORTANT: This function operates on the display subtitles (post-Granite
    correction), NOT on the original Whisper segments.  AI Analysis (genre,
    keywords, summary) has already been performed on the original transcript
    before this function is called.

    Args:
        subtitles: List of subtitle dicts with at minimum "id" and "text" keys.
                   These are the Granite-corrected display subtitles.

    Returns:
        A new list of subtitle dicts with the same structure, but "text"
        replaced with the English translation.  On any failure, the original
        Hindi text is preserved for all affected segments.
    """
    if not subtitles:
        return subtitles

    # Build minimal input for translation (id + text only)
    translate_input = [
        {"id": seg["id"], "text": seg["text"]}
        for seg in subtitles
    ]
    segments_json = json.dumps(translate_input, ensure_ascii=False, indent=2)

    try:
        logger.info(
            "Translating %d subtitle segment(s) Hindi → English via Granite (%s)",
            len(subtitles),
            config.OLLAMA_MODEL,
        )
        response = _call_ollama_translate(segments_json)

        translated_list = response.get("translated_segments")
        if not isinstance(translated_list, list):
            raise ValueError(
                f"Expected 'translated_segments' list, got: {type(translated_list)}"
            )

        # Build lookup: id → translated text
        translation_lookup: dict[int, str] = {}
        for item in translated_list:
            if isinstance(item, dict) and "id" in item and "text" in item:
                translation_lookup[int(item["id"])] = item["text"]

        # Merge translations back into subtitle dicts
        result = []
        for seg in subtitles:
            seg_id = int(seg["id"])
            if seg_id in translation_lookup:
                translated_text = translation_lookup[seg_id]
                result.append({**seg, "text": translated_text})
            else:
                # Fallback: keep original text for any segment Granite missed
                logger.warning(
                    "Translation missing for segment id=%d — keeping original text",
                    seg_id,
                )
                result.append(seg)

        logger.info(
            "Translation complete — %d/%d segments translated",
            len(translation_lookup),
            len(subtitles),
        )
        return result

    except RuntimeError as exc:
        logger.warning("Translation failed (Ollama error): %s — keeping original text", exc)
        return subtitles
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Translation failed (parse error): %s — keeping original text", exc)
        return subtitles
    except Exception as exc:
        logger.exception("Unexpected translation error — keeping original text")
        return subtitles
