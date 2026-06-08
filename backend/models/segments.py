from typing import List, Optional

from pydantic import BaseModel


class SegmentBreakdown(BaseModel):
    segment_index: int
    script_line: str
    start_time: float
    end_time: float
    duration: float
    effect: str = "none"
    image_path: Optional[str] = None
    segment_prompt: Optional[str] = None
    characters_present: Optional[List[str]] = None


class Segments(BaseModel):
    segments: List[SegmentBreakdown]


class SegmentPrompt(BaseModel):
    segment_index: int
    script_line: str
    segment_prompt: str
    characters_present: List[str]
    start_time: float
    end_time: float
    duration: float
    effect: str = "none"
    image_path: Optional[str] = None


class SegmentPrompts(BaseModel):
    segments: List[SegmentPrompt]


class SplitRequest(BaseModel):
    word_index: Optional[int] = None
    timestamp: Optional[float] = None


class SegmentEffectUpdate(BaseModel):
    effect: str
