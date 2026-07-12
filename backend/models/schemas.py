"""
Pydantic schemas for CaptainAI.

Sub-task 4 additions:
- LanguageProfile: global language assessment from Granite.
- GenreResult:     genre label + self-reported confidence.
- GraniteResult:   full structured output from the Granite processor, saved as
                   granite_result.json.  This is the schema for Sub-task 4.
- ProcessedResult updated to include language_profile, genre as rich objects,
  and style_preset name alongside the full StylePreset object.
"""

from pydantic import BaseModel
from typing import Literal


class JobStatus(BaseModel):
    job_id: str
    stage: str
    pct: int
    error: str | None = None


class Segment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    corrected_text: str
    language: Literal["en", "hi", "hi-en"]


class StylePreset(BaseModel):
    preset_name: str
    font_name: str
    font_size: int
    primary_color: str
    outline_color: str
    position: str
    background_box: bool
    bold: bool


# ── Sub-task 4: Granite result sub-schemas ────────────────────────────────────

class LanguageProfile(BaseModel):
    """
    Global language assessment for the whole video content.

    primary_language:   Dominant language code ("en", "hi", "hi-en", etc.).
    secondary_language: Present when code-switching involves a clearly distinct
                        secondary language; null otherwise.
    contains_code_switching: True when the speaker mixes languages mid-sentence
                             or across segments (e.g. Hinglish).
    """
    primary_language: str
    secondary_language: str | None = None
    contains_code_switching: bool


class GenreResult(BaseModel):
    """
    Genre classification from Granite.

    label:      One of "study", "talk", "song", "vlog".
    confidence: The model's own self-reported confidence estimate (0.0–1.0).
                This is NOT a statistically calibrated probability — it is the
                model's subjective certainty expressed as a float.  Treat it
                as a soft indicator, not a precise score.
    """
    label: Literal["study", "talk", "song", "vlog"]
    confidence: float


class CorrectedSegment(BaseModel):
    """A single Granite-corrected segment (text only — no timestamps)."""
    id: int
    corrected_text: str


class GraniteResult(BaseModel):
    """
    Full structured output from the Granite processor.

    Saved as ``granite_result.json`` in the job directory.
    Timestamps are NOT included — those belong to WhisperSegments only.
    """
    corrected_segments: list[CorrectedSegment]
    language_profile: LanguageProfile
    genre: GenreResult
    keywords: list[str]
    style_preset: Literal["cinematic", "social", "education", "minimal"]
    summary: str


# ── ProcessedResult (full pipeline output) ────────────────────────────────────

class ProcessedResult(BaseModel):
    """
    Complete result available after the full pipeline completes (Sub-tasks 3+4).

    segments:             Whisper segments enriched with corrected_text.
    language_profile:     Global language assessment from Granite.
    genre:                Genre label + confidence from Granite.
    keywords:             Relevant topic keywords extracted by Granite.
    style_recommendation: The resolved StylePreset for the recommended preset.
    style_preset_name:    The preset name string ("cinematic", "social", etc.).
    granite_summary:      One–two sentence summary from Granite.
    """
    segments: list[Segment]
    language_profile: LanguageProfile
    genre: GenreResult
    keywords: list[str]
    style_recommendation: StylePreset
    style_preset_name: str
    granite_summary: str


class ExportRequest(BaseModel):
    segments: list[Segment]
    style: StylePreset
    formats: list[str]
