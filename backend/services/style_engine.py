"""
Style engine — genre-to-preset mapping, StylePreset definitions, and FFmpeg
force_style string generation.

Sub-task 4 scope: define presets and the genre→preset lookup used by the
Granite processor.

Sub-task 7 addition: `to_force_style_string()` — converts a StylePreset into
the FFmpeg `subtitles` filter `force_style` parameter value.

Karaoke is a MANUAL-ONLY preset. It is NEVER returned by get_preset_for_genre()
and Granite is explicitly instructed not to emit it.

Genre → preset mapping:
  study  → education
  talk   → minimal
  song   → cinematic
  vlog   → social

FFmpeg force_style colour format:
  FFmpeg uses BGR order in the format &HAABBGGRR (Alpha-Blue-Green-Red),
  not the standard HTML #RRGGBB.  Converting correctly is critical — using
  the wrong order produces the wrong colour (e.g. red becomes blue).

  The frontend stores colours as standard HTML hex strings (#RRGGBB), so
  `to_force_style_string()` must convert them.

  Examples:
    HTML white  #FFFFFF  →  FFmpeg &H00FFFFFF   (AA=00, BB=FF, GG=FF, RR=FF)
    HTML yellow #FFFF00  →  FFmpeg &H0000FFFF   (AA=00, BB=00, GG=FF, RR=FF)
    HTML black  #000000  →  FFmpeg &H00000000
    HTML cyan   #00FFFF  →  FFmpeg &H00FFFF00
    HTML blue   #0000FF  →  FFmpeg &H00FF0000

Alignment values (ASS / FFmpeg):
    1=bottom-left  2=bottom-center  3=bottom-right
    4=mid-left     5=mid-center     6=mid-right
    7=top-left     8=top-center     9=top-right
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


# ── Colour helpers ────────────────────────────────────────────────────────────

def _html_hex_to_ffmpeg_bgr(html_color: str) -> str:
    """
    Convert an HTML hex colour string to FFmpeg ASS colour format.

    Input:  "#RRGGBB" or "RRGGBB" (with or without leading #)
    Output: "&H00BBGGRR"  (Alpha=00, Blue, Green, Red)

    If the input is already in FFmpeg format ("&H..."), it is returned as-is.
    """
    if html_color.startswith("&H") or html_color.startswith("&h"):
        return html_color  # already FFmpeg format — pass through

    color = html_color.lstrip("#")
    if len(color) == 6:
        r = color[0:2]
        g = color[2:4]
        b = color[4:6]
        return f"&H00{b}{g}{r}".upper()

    # Fallback to white if format is unrecognised
    return "&H00FFFFFF"


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


def to_force_style_string(style: StylePreset) -> str:
    """
    Build the FFmpeg ``force_style`` parameter string from a StylePreset.

    This string is passed as the ``force_style`` option of the FFmpeg
    ``subtitles=`` filter.  It overrides the style embedded in the SRT file
    (SRT has no style spec) and applies the user's chosen look to the burn-in.

    Example output:
        FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,
        OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,Bold=0

    Alignment mapping:
        position="bottom"  →  Alignment=2  (bottom-center)
        position="top"     →  Alignment=8  (top-center)
        anything else      →  Alignment=2  (safe fallback)

    BorderStyle:
        background_box=True  →  BorderStyle=3  (opaque background box)
        background_box=False →  BorderStyle=1  (outline + shadow, no box)
    """
    primary_colour  = _html_hex_to_ffmpeg_bgr(style.primary_color)
    outline_colour  = _html_hex_to_ffmpeg_bgr(style.outline_color)

    alignment     = 8 if style.position == "top" else 2
    border_style  = 3 if style.background_box else 1
    bold_flag     = 1 if style.bold else 0
    outline_width = 0 if style.background_box else 2

    return (
        f"FontName={style.font_name}"
        f",FontSize={style.font_size}"
        f",PrimaryColour={primary_colour}"
        f",OutlineColour={outline_colour}"
        f",BorderStyle={border_style}"
        f",Outline={outline_width}"
        f",Alignment={alignment}"
        f",Bold={bold_flag}"
    )
