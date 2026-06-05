import os
import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.fireworks import FireworksClient
from services.state import get_state, update_state
from services.effects import validate_effect
from models.state import ProjectState
from config import PROJECTS_BASE_DIR

segments_router = APIRouter()


class SegmentBreakdown(BaseModel):
    segment_index: int
    script_line: str
    start_time: float
    end_time: float
    duration: float
    effect: str = "none"


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


class SegmentPrompts(BaseModel):
    segments: List[SegmentPrompt]


class SplitRequest(BaseModel):
    word_index: Optional[int] = None
    timestamp: Optional[float] = None


class SegmentEffectUpdate(BaseModel):
    effect: str


def _get_project_dir(uuid: str) -> str:
    return os.path.join(PROJECTS_BASE_DIR, uuid)


def _get_conduit_dir(uuid: str) -> str:
    return os.path.join(_get_project_dir(uuid), ".conduit")


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _is_token_limit_error(exc: Exception) -> bool:
    """Detect if an exception indicates a token limit or request too long."""
    status_code = getattr(exc, "status_code", None)
    if status_code == 413:
        return True
    message = str(exc).lower()
    token_keywords = ["token limit", "too many tokens", "max tokens", "context length", "too long"]
    return any(kw in message for kw in token_keywords)


def _build_segment_prompts_prompt(segments_batch: List[dict], characters_data: dict) -> str:
    """Build the prompt for segment prompt generation."""
    characters = []
    if isinstance(characters_data, dict):
        characters = characters_data.get("characters", [])

    prompt = (
        "You are given a list of video segments and a list of characters. "
        "For each segment, generate an image generation prompt that describes the visual scene, "
        "and identify which characters from the character list are present in that segment. "
        "Return the result as a JSON object with a 'segments' array. "
        "Each segment must include: segment_index, script_line, segment_prompt, characters_present, start_time, end_time, duration.\n\n"
    )

    if characters:
        prompt += "Characters:\n" + json.dumps(characters, indent=2) + "\n\n"
    else:
        prompt += "Characters: (none identified)\n\n"

    prompt += "Segments:\n" + json.dumps(segments_batch, indent=2)
    return prompt


async def _generate_prompts_for_batch(
    segments_batch: List[dict],
    characters_data: dict,
    client: FireworksClient,
) -> List[dict]:
    """Generate prompts for a single batch of segments."""
    prompt = _build_segment_prompts_prompt(segments_batch, characters_data)
    result = await client.chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates image prompts for video segments."},
            {"role": "user", "content": prompt},
        ],
        json_schema=SegmentPrompts,
        max_tokens=4096,
    )
    if not isinstance(result, dict) or "segments" not in result:
        raise ValueError("Invalid response from Fireworks AI: missing 'segments'")
    return result["segments"]


async def _generate_prompts_in_batches(
    segments: List[dict],
    characters_data: dict,
    client: FireworksClient,
) -> List[dict]:
    """Fallback: generate prompts in overlapping batches."""
    batch_size = 25
    overlap = 5
    result_map: dict = {}
    i = 0
    while i < len(segments):
        batch = segments[i : i + batch_size]
        batch_results = await _generate_prompts_for_batch(batch, characters_data, client)
        for seg in batch_results:
            result_map[seg["segment_index"]] = seg
        i += batch_size - overlap
    return [result_map[seg["segment_index"]] for seg in segments if seg["segment_index"] in result_map]


def _ensure_step_2_complete(uuid: str) -> None:
    """Validate that the project is at least at step_2_complete."""
    # Note: we cannot use async get_state here because this is a sync helper.
    # The caller should do the async check before calling this.
    pass


@segments_router.post("/projects/{uuid}/segments/breakdown", response_model=Segments)
async def breakdown_segments(uuid: str):
    """Break down script into segments using Fireworks AI.

    Reads source_of_truth_script.txt and words.json from the project directory,
    sends them to Fireworks AI for segment breakdown, saves segments.json,
    and updates the sub-step state in state.json.
    """
    # Validate project state
    current_state = await get_state(uuid)
    if current_state not in (ProjectState.STEP_2_COMPLETE, ProjectState.STEP_3_COMPLETE, ProjectState.STEP_4_COMPLETE, ProjectState.STEP_5_COMPLETE):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prerequisites not met: project must be at least at step_2_complete",
        )

    conduit_dir = _get_conduit_dir(uuid)

    script_path = os.path.join(conduit_dir, "source_of_truth_script.txt")
    words_path = os.path.join(conduit_dir, "words.json")

    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing source_of_truth_script.txt",
        )
    if not os.path.exists(words_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing words.json",
        )

    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read()

    words_data = _load_json(words_path)
    words = words_data.get("words", words_data)

    # Build prompt
    prompt = (
        "You are given a voiceover script and a list of transcribed words with timestamps. "
        "Break the script into logical segments (e.g., sentences or phrases). "
        "For each segment, provide the exact script line, the start time (from the first word), "
        "the end time (from the last word), and the duration. "
        "Return the result as a JSON object with a 'segments' array.\n\n"
        "Script:\n" + script_text + "\n\n"
        "Words with timestamps:\n" + json.dumps(words, indent=2)
    )

    client = FireworksClient()
    try:
        result = await client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that breaks scripts into timed segments."},
                {"role": "user", "content": prompt},
            ],
            json_schema=Segments,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fireworks API failure: {exc}",
        )

    if not isinstance(result, dict) or "segments" not in result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from Fireworks AI: missing 'segments'",
        )

    segments = result["segments"]
    # Ensure each segment has a segment_index and effect
    for i, seg in enumerate(segments):
        seg["segment_index"] = i
        seg.setdefault("effect", "none")

    # Save segments.json
    segments_path = os.path.join(conduit_dir, "segments.json")
    _save_json(segments_path, {"segments": segments})

    # Update state.json sub-step
    state_json_path = os.path.join(conduit_dir, "state.json")
    if os.path.exists(state_json_path):
        state_data = _load_json(state_json_path)
        state_data["step_3_pass_1_complete"] = True
        _save_json(state_json_path, state_data)

    return Segments(segments=[SegmentBreakdown(**seg) for seg in segments])


@segments_router.put("/projects/{uuid}/segments", response_model=Segments)
async def update_segments(uuid: str, segments_data: Segments):
    """Accept an edited segment list and write it to segments.json."""
    conduit_dir = _get_conduit_dir(uuid)
    segments_path = os.path.join(conduit_dir, "segments.json")

    # Re-index segments to ensure consistency
    segments_list = []
    for i, seg in enumerate(segments_data.segments):
        seg_dict = seg.model_dump()
        seg_dict["segment_index"] = i
        segments_list.append(seg_dict)

    _save_json(segments_path, {"segments": segments_list})

    return Segments(segments=[SegmentBreakdown(**seg) for seg in segments_list])


@segments_router.post("/projects/{uuid}/segments/{segment_index}/split", response_model=Segments)
async def split_segment(uuid: str, segment_index: int, request: SplitRequest):
    """Split a segment into two at the specified word index or timestamp."""
    conduit_dir = _get_conduit_dir(uuid)
    segments_path = os.path.join(conduit_dir, "segments.json")

    if not os.path.exists(segments_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="segments.json not found",
        )

    data = _load_json(segments_path)
    segments = [SegmentBreakdown(**seg) for seg in data.get("segments", [])]

    if segment_index < 0 or segment_index >= len(segments):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid segment_index",
        )

    seg = segments[segment_index]

    # Determine split point
    if request.timestamp is not None:
        split_point = request.timestamp
        if split_point <= seg.start_time or split_point >= seg.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Split timestamp must be within segment bounds",
            )
    elif request.word_index is not None:
        # Load words.json to find timestamp at word index
        words_path = os.path.join(conduit_dir, "words.json")
        if not os.path.exists(words_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="words.json not found",
            )
        words_data = _load_json(words_path)
        words = words_data.get("words", words_data)
        if request.word_index < 0 or request.word_index >= len(words):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid word_index",
            )
        split_point = words[request.word_index]["start"]
        if split_point <= seg.start_time or split_point >= seg.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Split point must be within segment bounds",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either word_index or timestamp must be provided",
        )

    # Split the segment
    left_seg = seg.model_dump()
    right_seg = seg.model_dump()

    left_seg["end_time"] = split_point
    left_seg["duration"] = split_point - seg.start_time

    right_seg["start_time"] = split_point
    right_seg["duration"] = seg.end_time - split_point

    # Replace original segment with two new segments
    segments.pop(segment_index)
    segments.insert(segment_index, SegmentBreakdown(**right_seg))
    segments.insert(segment_index, SegmentBreakdown(**left_seg))

    # Re-index
    for i, s in enumerate(segments):
        s.segment_index = i

    # Save
    segments_list = [s.model_dump() for s in segments]
    _save_json(segments_path, {"segments": segments_list})

    return Segments(segments=segments)


@segments_router.post("/projects/{uuid}/segments/{segment_index}/merge", response_model=Segments)
async def merge_segment(uuid: str, segment_index: int):
    """Merge a segment with the next segment."""
    conduit_dir = _get_conduit_dir(uuid)
    segments_path = os.path.join(conduit_dir, "segments.json")

    if not os.path.exists(segments_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="segments.json not found",
        )

    data = _load_json(segments_path)
    segments = [SegmentBreakdown(**seg) for seg in data.get("segments", [])]

    if segment_index < 0 or segment_index >= len(segments) - 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid segment_index: cannot merge last segment",
        )

    seg = segments[segment_index]
    next_seg = segments[segment_index + 1]

    merged = seg.model_dump()
    merged["script_line"] = seg.script_line + " " + next_seg.script_line
    merged["end_time"] = next_seg.end_time
    merged["duration"] = next_seg.end_time - seg.start_time

    # Replace two segments with merged
    segments.pop(segment_index + 1)
    segments.pop(segment_index)
    segments.insert(segment_index, SegmentBreakdown(**merged))

    # Re-index
    for i, s in enumerate(segments):
        s.segment_index = i

    # Save
    segments_list = [s.model_dump() for s in segments]
    _save_json(segments_path, {"segments": segments_list})

    return Segments(segments=segments)


@segments_router.get("/projects/{uuid}/segments", response_model=Segments)
async def get_segments(uuid: str):
    """Get all segments for a project."""
    conduit_dir = _get_conduit_dir(uuid)
    segments_path = os.path.join(conduit_dir, "segments.json")

    if not os.path.exists(segments_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="segments.json not found",
        )

    data = _load_json(segments_path)
    segments = [SegmentBreakdown(**seg) for seg in data.get("segments", [])]
    return Segments(segments=segments)


@segments_router.put("/projects/{uuid}/segments/{segment_index}/effect")
async def update_segment_effect(uuid: str, segment_index: int, request: SegmentEffectUpdate):
    """Update the effect for a specific segment."""
    if not validate_effect(request.effect):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid effect: {request.effect}",
        )

    conduit_dir = _get_conduit_dir(uuid)
    segments_path = os.path.join(conduit_dir, "segments.json")

    if not os.path.exists(segments_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="segments.json not found",
        )

    data = _load_json(segments_path)
    segments = data.get("segments", [])

    if segment_index < 0 or segment_index >= len(segments):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid segment_index",
        )

    segments[segment_index]["effect"] = request.effect
    _save_json(segments_path, {"segments": segments})

    return {"segment_index": segment_index, "effect": request.effect}


@segments_router.post("/projects/{uuid}/segments/prompts", response_model=SegmentPrompts)
async def generate_segment_prompts(uuid: str):
    """Generate image prompts for each segment using Fireworks AI.

    Reads segments.json and characters.json, sends them to Fireworks AI
    for prompt generation, updates segments.json with prompts, and
    advances the project state.
    """
    # Validate project state
    current_state = await get_state(uuid)
    if current_state not in (
        ProjectState.STEP_2_COMPLETE,
        ProjectState.STEP_3_COMPLETE,
        ProjectState.STEP_4_COMPLETE,
        ProjectState.STEP_5_COMPLETE,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prerequisites not met: project must be at least at step_2_complete",
        )

    conduit_dir = _get_conduit_dir(uuid)
    segments_path = os.path.join(conduit_dir, "segments.json")
    characters_path = os.path.join(conduit_dir, "characters.json")

    if not os.path.exists(segments_path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Segment breakdown required first",
        )

    segments_data = _load_json(segments_path)
    segments = segments_data.get("segments", [])
    if not segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No segments found",
        )

    characters_data = {}
    if os.path.exists(characters_path):
        characters_data = _load_json(characters_path)

    client = FireworksClient()
    try:
        result = await _generate_prompts_for_batch(segments, characters_data, client)
    except Exception as exc:
        if _is_token_limit_error(exc):
            try:
                result = await _generate_prompts_in_batches(segments, characters_data, client)
            except Exception as batch_exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Fireworks API failure: {batch_exc}",
                ) from batch_exc
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Fireworks API failure: {exc}",
            ) from exc

    # Build a map of segment_index -> result
    result_map = {seg["segment_index"]: seg for seg in result}

    # Update original segments with prompts
    updated_segments = []
    for seg in segments:
        idx = seg.get("segment_index")
        if idx in result_map:
            seg["segment_prompt"] = result_map[idx].get("segment_prompt", "")
            seg["characters_present"] = result_map[idx].get("characters_present", [])
        else:
            seg.setdefault("segment_prompt", "")
            seg.setdefault("characters_present", [])
        seg.setdefault("effect", "none")
        updated_segments.append(seg)

    # Save segments.json (preserves breakdown data, adds prompts)
    _save_json(segments_path, {"segments": updated_segments})

    # Update main SQLite state to step_3_complete if currently at step_2_complete
    if current_state == ProjectState.STEP_2_COMPLETE:
        try:
            await update_state(uuid, ProjectState.STEP_3_COMPLETE)
        except HTTPException:
            # If state transition fails (e.g., already updated), ignore
            pass

    # Update sub-step state in state.json
    state_json_path = os.path.join(conduit_dir, "state.json")
    if os.path.exists(state_json_path):
        state_data = _load_json(state_json_path)
        state_data["step_3_pass_2_complete"] = True
        _save_json(state_json_path, state_data)

    return SegmentPrompts(segments=[SegmentPrompt(**seg) for seg in updated_segments])
