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


class ProcessedResult(BaseModel):
    segments: list[Segment]
    genre: str
    keywords: list[str]
    style_recommendation: StylePreset
    granite_summary: str


class ExportRequest(BaseModel):
    segments: list[Segment]
    style: StylePreset
    formats: list[str]
