import logging
import os
import json
import uuid
_uuid_module = uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, status
from openai._exceptions import AuthenticationError, APITimeoutError, RateLimitError, APIError

from models.segments import (
    SegmentBreakdown,
    Segments,
    SegmentPrompt,
    SegmentPrompts,
    SplitRequest,
    SegmentEffectUpdate,
)
from services.fireworks import FireworksClient
from services.state import get_state, update_state, get_style_id
from services.effects import validate_effect
from services.prompts import (
    build_segment_breakdown_messages,
    build_segment_prompts_messages,
    get_style,
)
from models.state import ProjectState
from config import PROJECTS_BASE_DIR

segments_router = APIRouter()

BREAKDOWN_MAX_TOKENS = 16000
SEGMENT_PROMPTS_MAX_TOKENS = 16000
SEGMENT_PROMPT_BATCH_SIZE = int(os.environ.get("CONDUIT_SEGMENT_BATCH_SIZE", 12))
SEGMENT_PROMPT_BATCH_OVERLAP = int(os.environ.get("CONDUIT_SEGMENT_BATCH_OVERLAP", 5))


def _handle_fireworks_error(exc: Exception) -> None:
    """Map Fireworks/OpenAI exceptions to HTTPExceptions."""
    if isinstance(exc, AuthenticationError):
        logging.error("AI authentication failed", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service authentication failed",
        ) from exc
    if isinstance(exc, RateLimitError):
        logging.error("AI rate limited", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI service rate limited, retry shortly",
        ) from exc
    if isinstance(exc, APITimeoutError):
        logging.error("AI request timed out", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI provider timed out — try again or increase FIREWORKS_TIMEOUT",
        ) from exc
    if isinstance(exc, APIError):
        logging.error("AI request failed", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI request failed",
        ) from exc
    raise exc


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


def _merge_prompts_into_segments(segments: List[dict], batch_results: List[dict]) -> None:
    result_map = {r["segment_index"]: r for r in batch_results
                  if isinstance(r, dict) and "segment_index" in r}
    for seg in segments:
        idx = seg.get("segment_index")
        if idx in result_map:
            seg["segment_prompt"] = result_map[idx].get("segment_prompt", "")
            seg["characters_present"] = result_map[idx].get("characters_present", [])
        seg.setdefault("segment_prompt", "")
        seg.setdefault("characters_present", [])
        seg.setdefault("effect", "none")


async def _generate_prompts_for_batch(
    segments_batch: List[dict],
    characters_data: dict,
    client: FireworksClient,
    uuid: str,
) -> List[dict]:
    """Generate prompts for a single batch of segments."""
    style = get_style(get_style_id(uuid))
    messages = build_segment_prompts_messages(segments_batch, characters_data, style)
    result = await client.chat_completion(
        messages=messages,
        json_schema=SegmentPrompts,
        max_tokens=SEGMENT_PROMPTS_MAX_TOKENS,
    )
    if not isinstance(result, dict) or "segments" not in result:
        raise ValueError("Invalid response from Fireworks AI: missing 'segments'")
    return result["segments"]


async def _generate_and_persist_prompts(segments, characters_data, client, uuid, segments_path):
    batch_size = max(1, SEGMENT_PROMPT_BATCH_SIZE)
    overlap = max(0, min(SEGMENT_PROMPT_BATCH_OVERLAP, batch_size - 1))
    step = batch_size - overlap
    pending = [s for s in segments if not s.get("segment_prompt")]
    i = 0
    while i < len(pending):
        batch = pending[i : i + batch_size]
        batch_results = await _generate_prompts_for_batch(batch, characters_data, client, uuid)
        _merge_prompts_into_segments(segments, batch_results)
        _save_json(segments_path, {"segments": segments})   # persist after EACH batch
        i += step
    return segments


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

    messages = build_segment_breakdown_messages(script_text, json.dumps(words, indent=2))

    client = FireworksClient()
    try:
        result = await client.chat_completion(
            messages=messages,
            json_schema=Segments,
            max_tokens=BREAKDOWN_MAX_TOKENS,
        )
    except (AuthenticationError, RateLimitError, APIError) as exc:
        _handle_fireworks_error(exc)

    if not isinstance(result, dict) or "segments" not in result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from Fireworks AI: missing 'segments'",
        )

    segments = result["segments"]
    # Ensure each segment has a segment_index, effect, and segment_id
    for i, seg in enumerate(segments):
        seg["segment_index"] = i
        seg.setdefault("effect", "none")
        seg["segment_id"] = str(_uuid_module.uuid4())

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


@segments_router.put("/projects/{uuid}/segments")
async def update_segments(uuid: str, segments_data: dict = Body(...)):
    """Accept an edited segment list and write it to segments.json.

    Client edits win; omitted fields are preserved from disk.
    """
    conduit_dir = _get_conduit_dir(uuid)
    segments_path = os.path.join(conduit_dir, "segments.json")

    incoming = segments_data.get("segments", [])

    # Load existing segments to preserve omitted fields
    on_disk = []
    if os.path.exists(segments_path):
        on_disk = _load_json(segments_path).get("segments", [])

    # Merge incoming over on-disk; client edits win, omitted fields preserved
    merged = []
    for i, incoming_seg in enumerate(incoming):
        base = on_disk[i] if i < len(on_disk) else {}
        merged_seg = {**base, **incoming_seg}
        merged_seg["segment_index"] = i
        if not merged_seg.get("segment_id"):
            merged_seg["segment_id"] = str(_uuid_module.uuid4())
        merged.append(merged_seg)

    _save_json(segments_path, {"segments": merged})
    return {"segments": merged}


@segments_router.post("/projects/{uuid}/segments/{segment_index}/split")
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
    segments = data.get("segments", [])

    if segment_index < 0 or segment_index >= len(segments):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid segment_index",
        )

    seg = segments[segment_index]

    # Determine split point
    if request.timestamp is not None:
        split_point = request.timestamp
        if split_point <= seg["start_time"] or split_point >= seg["end_time"]:
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
        if split_point <= seg["start_time"] or split_point >= seg["end_time"]:
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
    left_seg = dict(seg)
    right_seg = dict(seg)

    left_seg["segment_id"] = str(_uuid_module.uuid4())
    right_seg["segment_id"] = str(_uuid_module.uuid4())

    left_seg["end_time"] = split_point
    left_seg["duration"] = split_point - seg["start_time"]

    right_seg["start_time"] = split_point
    right_seg["duration"] = seg["end_time"] - split_point

    # Reset prompt fields on both halves
    left_seg["segment_prompt"] = ""
    left_seg["characters_present"] = []
    left_seg.pop("image_path", None)
    right_seg["segment_prompt"] = ""
    right_seg["characters_present"] = []
    right_seg.pop("image_path", None)

    # Replace original segment with two new segments
    segments[segment_index : segment_index + 1] = [left_seg, right_seg]

    # Re-index
    for i, s in enumerate(segments):
        s["segment_index"] = i

    # Save
    _save_json(segments_path, {"segments": segments})

    return {"segments": segments}


@segments_router.post("/projects/{uuid}/segments/{segment_index}/merge")
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
    segments = data.get("segments", [])

    if segment_index < 0 or segment_index >= len(segments) - 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid segment_index: cannot merge last segment",
        )

    seg = segments[segment_index]
    next_seg = segments[segment_index + 1]

    merged = dict(seg)
    merged["segment_id"] = str(_uuid_module.uuid4())
    merged["script_line"] = seg["script_line"] + " " + next_seg["script_line"]
    merged["end_time"] = next_seg["end_time"]
    merged["duration"] = next_seg["end_time"] - seg["start_time"]

    # Keep effect from first segment (already copied via dict(seg))
    # Reset prompt fields on merged segment
    merged["segment_prompt"] = ""
    merged["characters_present"] = []
    merged.pop("image_path", None)

    # Replace two segments with merged
    segments[segment_index : segment_index + 2] = [merged]

    # Re-index
    for i, s in enumerate(segments):
        s["segment_index"] = i

    # Save
    _save_json(segments_path, {"segments": segments})

    return {"segments": segments}


@segments_router.get("/projects/{uuid}/segments")
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
    segments = data.get("segments", [])
    return {"segments": segments}


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
    characters_path = os.path.join(_get_project_dir(uuid), "characters.json")

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
        segments = await _generate_and_persist_prompts(segments, characters_data, client, uuid, segments_path)
    except (AuthenticationError, RateLimitError, APIError, ValueError) as exc:
        if isinstance(exc, ValueError):
            logging.error("AI returned an unexpected response", exc_info=exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI returned an unexpected response",
            ) from exc
        _handle_fireworks_error(exc)

    # Only advance state if every segment now has a prompt
    if all(s.get("segment_prompt") for s in segments):
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

    return SegmentPrompts(segments=[SegmentPrompt(**seg) for seg in segments])


@segments_router.post("/projects/{uuid}/segments/{segment_index}/prompt", response_model=SegmentPrompt)
async def regenerate_segment_prompt(
    uuid: str,
    segment_index: int,
    character_versions: Optional[Dict[str, str]] = Body(default=None, embed=True),
):
    """Regenerate the image prompt for a single segment."""
    conduit_dir = _get_conduit_dir(uuid)
    segments_path = os.path.join(conduit_dir, "segments.json")
    characters_path = os.path.join(_get_project_dir(uuid), "characters.json")

    if not os.path.exists(segments_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="segments.json not found",
        )

    segments_data = _load_json(segments_path)
    segments = segments_data.get("segments", [])

    if segment_index < 0 or segment_index >= len(segments):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid segment_index",
        )

    target_segment = segments[segment_index]

    characters_data = {}
    if os.path.exists(characters_path):
        characters_data = _load_json(characters_path)

    if character_versions is not None and characters_data:
        filtered_chars = []
        for char in characters_data.get("characters", []):
            base_name = char.get("base_name", "")
            if base_name in character_versions:
                # character_versions maps base_name -> version name (the unique `name` field)
                if char.get("name", "") == character_versions[base_name]:
                    filtered_chars.append(char)
            else:
                filtered_chars.append(char)
        characters_data = {"characters": filtered_chars}

    batch = [target_segment]

    client = FireworksClient()
    try:
        result = await _generate_prompts_for_batch(batch, characters_data, client, uuid)
    except (AuthenticationError, RateLimitError, APIError, ValueError) as exc:
        if isinstance(exc, ValueError):
            logging.error("AI returned an unexpected response", exc_info=exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI returned an unexpected response",
            ) from exc
        _handle_fireworks_error(exc)

    if not isinstance(result, list) or len(result) == 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from Fireworks AI: missing segment result",
        )

    updated = result[0]

    segments[segment_index]["segment_prompt"] = updated.get("segment_prompt", "")
    segments[segment_index]["characters_present"] = updated.get("characters_present", [])

    _save_json(segments_path, {"segments": segments})

    return SegmentPrompt(**segments[segment_index])
