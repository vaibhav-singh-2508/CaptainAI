"""
Style engine — genre-to-preset mapping and StylePreset definitions.

Sub-task 4 scope: define presets and the genre→preset lookup used by the
Granite processor.  The `to_force_style_string()` method (used for FFmpeg
burn-in) is left for Sub-task 7.

Karaoke is a MANUAL-ONLY preset. It is NEVER returned by get_preset_for_genre()
and Granite is explicitly instructed not to emit it.

Genre → preset mapping:
  study  → education
  talk   → minimal
  song   → cinematic
  vlog   → social
"""

from models.schemas import StylePreset

# ── Preset definitions ────────────────────────────────────────────────────────

_PRESETS: dict[str, StylePreset] = {
    "cinematic": StylePreset(
        preset_name="cinematic",
        font_name="Arial",
        font_size=28,
        primary_color="&H00FFFFFF",   # white
        outline_color="&H00000000",   # black
        position="bottom",
        background_box=False,
        bold=True,
    ),
    "social": StylePreset(
        preset_name="social",
        font_name="Arial",
        font_size=32,
        primary_color="&H00FFFF00",   # yellow
        outline_color="&H00000000",   # black
        position="bottom",
        background_box=True,
        bold=True,
    ),
    "education": StylePreset(
        preset_name="education",
        font_name="Arial",
        font_size=24,
        primary_color="&H00FFFFFF",   # white
        outline_color="&H000000FF",   # blue outline
        position="bottom",
        background_box=True,
        bold=False,
    ),
    "minimal": StylePreset(
        preset_name="minimal",
        font_name="Arial",
        font_size=22,
        primary_color="&H00FFFFFF",   # white
        outline_color="&H00000000",   # black
        position="bottom",
        background_box=False,
        bold=False,
    ),
    "karaoke": StylePreset(
        preset_name="karaoke",
        font_name="Arial",
        font_size=30,
        primary_color="&H0000FFFF",   # cyan
        outline_color="&H00000000",   # black
        position="bottom",
        background_box=False,
        bold=True,
    ),
}

_GENRE_TO_PRESET: dict[str, str] = {
    "study": "education",
    "talk":  "minimal",
    "song":  "cinematic",
    "vlog":  "social",
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_preset(name: str) -> StylePreset:
    """Return a StylePreset by name.  Raises KeyError for unknown names."""
    return _PRESETS[name]


def get_preset_for_genre(genre_label: str) -> StylePreset:
    """
    Map a Granite genre label to the appropriate StylePreset.

    Falls back to the 'minimal' preset for unknown genre labels.
    """
    preset_name = _GENRE_TO_PRESET.get(genre_label, "minimal")
    return _PRESETS[preset_name]


def get_default_style() -> StylePreset:
    """Return the default style preset (minimal)."""
    return _PRESETS["minimal"]
