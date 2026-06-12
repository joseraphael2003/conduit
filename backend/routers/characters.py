import logging
import os
import json

from fastapi import APIRouter, HTTPException, status
from openai._exceptions import AuthenticationError, APITimeoutError, RateLimitError, APIError
from pydantic import ValidationError

from models.characters import (
    CharacterList,
    CharacterDescription,
    CharacterPromptsList,
    FrontProfilePromptList,
    TurnaroundPromptList,
)
from services.fireworks import FireworksClient
from services.prompts import (
    build_character_extraction_messages,
    build_character_timeline_messages,
    build_front_profile_messages,
    build_turnaround_messages,
    get_style,
)
from services.state import (
    get_state,
    update_state,
    get_style_id,
    invalidate_downstream,
    set_sub_step_state,
)
from models.state import ProjectState
import routers.projects as _projects_module

characters_router = APIRouter()

# Mirrors segments.py BREAKDOWN/SEGMENT_PROMPTS_MAX_TOKENS; covers extract,
# timeline, and Call 2 prompt generation to prevent mid-JSON truncation 502s.
CHARACTER_PROMPTS_MAX_TOKENS = 16000


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


def _normalize_name(name: str) -> str:
    """Normalize character name for resilient matching.
    
    Preserves parenthetical distinctions (e.g. 'The Mother (impostor)'
    stays distinct from 'The Real Mother').
    """
    if not name:
        return ""
    return " ".join(name.lower().split())


@characters_router.post(
    "/projects/{project_uuid}/characters/extract",
    response_model=CharacterList,
)
async def extract_characters(project_uuid: str):
    """Extract characters from the project's source-of-truth script."""
    # Verify project exists
    current_state = await get_state(project_uuid)

    # Prerequisite: must be at least step_1_complete
    if current_state == ProjectState.CREATED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prerequisite step not met",
        )

    # Read script
    script_path = os.path.join(
        _projects_module.PROJECTS_BASE_DIR, project_uuid, ".conduit", "source_of_truth_script.txt"
    )
    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No script found",
        )

    with open(script_path, "r", encoding="utf-8") as f:
        script_content = f.read()

    if not script_content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No script found",
        )

    # Build extraction messages
    messages = build_character_extraction_messages(script_content)

    # Call Fireworks AI
    client = FireworksClient()
    try:
        result = await client.chat_completion(
            messages=messages,
            json_schema=CharacterList,
            max_tokens=CHARACTER_PROMPTS_MAX_TOKENS,
        )
    except (AuthenticationError, RateLimitError, APIError) as exc:
        _handle_fireworks_error(exc)

    # Validate BEFORE persisting
    try:
        validated = CharacterList(**result)
    except ValidationError as exc:
        logging.error("AI returned data in an unexpected format", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned data in an unexpected format",
        ) from exc

    # Set default version fields for projects that skip the timeline pass
    for char in validated.characters:
        if not char.base_name:
            char.base_name = char.name
        if not char.version_label:
            char.version_label = "default"
        char.version_index = 0

    # Save validated extraction result to characters.json
    project_dir = os.path.join(_projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(validated.model_dump(), f, indent=2)

    # Invalidate downstream before marking this sub-step complete
    await invalidate_downstream(project_uuid, 2)

    # Update sub-step state in state.json
    state_json_path = os.path.join(project_dir, ".conduit", "state.json")
    if os.path.exists(state_json_path):
        with open(state_json_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
        state_data["step_2_call_1_complete"] = True
        with open(state_json_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

    return validated


@characters_router.post(
    "/projects/{project_uuid}/characters/timeline",
    response_model=CharacterList,
)
async def generate_character_timeline(project_uuid: str):
    """Generate character timeline versions from the project's script."""
    # Verify project exists
    current_state = await get_state(project_uuid)

    # Prerequisite: must be at least step_1_complete
    if current_state == ProjectState.CREATED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prerequisite step not met",
        )

    # Read existing characters
    project_dir = os.path.join(_projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    if not os.path.exists(characters_path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Character extraction not completed",
        )

    with open(characters_path, "r", encoding="utf-8") as f:
        existing_data = json.load(f)

    characters = existing_data.get("characters", [])
    if not characters:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Character extraction not completed",
        )

    # Read script
    script_path = os.path.join(
        _projects_module.PROJECTS_BASE_DIR, project_uuid, ".conduit", "source_of_truth_script.txt"
    )
    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No script found",
        )

    with open(script_path, "r", encoding="utf-8") as f:
        script_content = f.read()

    if not script_content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No script found",
        )

    # Get style
    style_id = get_style_id(project_uuid)
    style = get_style(style_id)

    # Build timeline messages
    messages = build_character_timeline_messages(script_content, characters, style)

    # Call Fireworks AI
    client = FireworksClient()
    try:
        result = await client.chat_completion(
            messages=messages,
            json_schema=CharacterList,
            max_tokens=CHARACTER_PROMPTS_MAX_TOKENS,
        )
    except (AuthenticationError, RateLimitError, APIError) as exc:
        _handle_fireworks_error(exc)

    # Validate BEFORE persisting
    try:
        validated = CharacterList(**result)
    except ValidationError as exc:
        logging.error("AI returned data in an unexpected format", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned data in an unexpected format",
        ) from exc

    # Default base_name to name for entries lacking it
    for char in validated.characters:
        if not char.base_name:
            char.base_name = char.name

    # Guard: every entry name must be unique → disambiguate
    seen_names = set()
    for char in validated.characters:
        if char.name in seen_names:
            logging.warning("Disambiguating duplicate character name: %s", char.name)
            char.name = f"{char.name} ({char.version_index})"
        seen_names.add(char.name)

    # Guard: every original base_name/person must yield at least one version → backfill
    original_base_names = {}
    for char in characters:
        base = char.get("base_name", "") or char.get("name", "")
        original_base_names.setdefault(base, []).append(char)

    result_base_names = set(char.base_name for char in validated.characters)
    missing = set(original_base_names.keys()) - result_base_names
    for base_name in missing:
        logging.warning(
            "Timeline missing versions for base_name %s; backfilling from Call 1",
            base_name,
        )
        template = original_base_names[base_name][0]
        backfill = CharacterDescription(
            name=template.get("name", base_name),
            type=template.get("type", "speaking"),
            importance=template.get("importance", "minor"),
            description=template.get("description", ""),
            base_name=base_name,
            version_label="default",
            version_index=0,
            appears_from="",
            identity_anchor="",
        )
        validated.characters.append(backfill)

    # Guard: identity_anchor must be consistent per base_name → coalesce
    anchor_by_base = {}
    for char in validated.characters:
        if char.base_name not in anchor_by_base:
            anchor_by_base[char.base_name] = char.identity_anchor
        elif anchor_by_base[char.base_name] != char.identity_anchor:
            logging.warning(
                "Coalescing inconsistent identity_anchor for base_name %s",
                char.base_name,
            )
            char.identity_anchor = anchor_by_base[char.base_name]

    # Persist expanded list
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(validated.model_dump(), f, indent=2)

    # Invalidate downstream before marking timeline complete
    await invalidate_downstream(project_uuid, 2)

    # Update sub-step state
    set_sub_step_state(project_uuid, "step_2_timeline_complete", True)

    return validated


@characters_router.get(
    "/projects/{project_uuid}/characters",
)
async def get_characters(project_uuid: str):
    """Retrieve the project's character list from characters.json.

    Returns the raw dict (no response_model) so persisted fields the
    CharacterDescription schema does not declare — front_profile_prompt and
    turnaround_prompt — survive on read. (Mirrors the 0.8.1 get_segments fix.)
    """
    project_dir = os.path.join(_projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    if not os.path.exists(characters_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="characters.json not found",
        )
    with open(characters_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Normalize version-field defaults on the raw dict so legacy (pre-version)
    # files load consistently — mirrors the CharacterDescription defaults the
    # old response_model applied — WITHOUT stripping extra persisted keys
    # (front_profile_prompt / turnaround_prompt).
    for char in data.get("characters", []):
        if not char.get("base_name"):
            char["base_name"] = char.get("name", "")
        char.setdefault("version_label", "default")
        char.setdefault("version_index", 0)
        char.setdefault("appears_from", "")
        char.setdefault("identity_anchor", "")
    return data


@characters_router.put(
    "/projects/{project_uuid}/characters",
    response_model=CharacterList,
)
async def update_characters(project_uuid: str, characters: CharacterList):
    """Accept an edited character list and persist it to characters.json."""
    # Re-derive base_name defaults for any entry missing it
    for char in characters.characters:
        if not char.base_name:
            char.base_name = char.name

    project_dir = os.path.join(_projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(characters.model_dump(), f, indent=2)

    await invalidate_downstream(project_uuid, 2)
    return characters


@characters_router.post(
    "/projects/{project_uuid}/characters/prompts",
    response_model=CharacterPromptsList,
)
async def generate_prompts(project_uuid: str):
    """Generate front-profile and turnaround prompts for each character."""
    # Read characters.json (must exist from Call 1)
    project_dir = os.path.join(_projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    if not os.path.exists(characters_path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Character extraction not completed",
        )

    with open(characters_path, "r", encoding="utf-8") as f:
        existing_data = json.load(f)

    characters = existing_data.get("characters", [])
    if not characters:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Character extraction not completed",
        )

    # Get style
    style_id = get_style_id(project_uuid)
    style = get_style(style_id)

    # Build messages for two batch calls
    front_messages = build_front_profile_messages(characters, style)
    turnaround_messages = build_turnaround_messages(characters, style)

    # Call Fireworks AI — two batch calls
    client = FireworksClient()
    try:
        front_result = await client.chat_completion(
            messages=front_messages,
            json_schema=FrontProfilePromptList,
            max_tokens=CHARACTER_PROMPTS_MAX_TOKENS,
        )
        turnaround_result = await client.chat_completion(
            messages=turnaround_messages,
            json_schema=TurnaroundPromptList,
            max_tokens=CHARACTER_PROMPTS_MAX_TOKENS,
        )
    except (AuthenticationError, RateLimitError, APIError) as exc:
        _handle_fireworks_error(exc)

    # Merge by normalized name — positional fallback if counts match
    front_chars = front_result.get("characters", [])
    turnaround_chars = turnaround_result.get("characters", [])

    front_by_name = {}
    for c in front_chars:
        norm = _normalize_name(c.get("name", ""))
        if norm in front_by_name:
            logging.warning("Duplicate normalized front-profile name %r", norm)
        front_by_name[norm] = c

    turnaround_by_name = {}
    for c in turnaround_chars:
        norm = _normalize_name(c.get("name", ""))
        if norm in turnaround_by_name:
            logging.warning("Duplicate normalized turnaround name %r", norm)
        turnaround_by_name[norm] = c

    counts_match = (
        len(front_chars) == len(characters) == len(turnaround_chars)
    )

    for idx, char in enumerate(characters):
        name = char.get("name")
        norm = _normalize_name(name)
        front = front_by_name.get(norm)
        turnaround = turnaround_by_name.get(norm)

        if not front or not turnaround:
            if counts_match:
                logging.warning(
                    "Prompts merge: name %r not found by normalized match, "
                    "using positional fallback at index %d",
                    name, idx,
                )
                if not front:
                    front = front_chars[idx]
                if not turnaround:
                    turnaround = turnaround_chars[idx]
            else:
                logging.error(
                    "Prompts merge: name %r missing and counts don't match "
                    "(front=%d, turnaround=%d, expected=%d)",
                    name, len(front_chars), len(turnaround_chars), len(characters),
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI returned incomplete character prompts",
                )

        char["front_profile_prompt"] = front.get("front_profile_prompt", "")
        char["turnaround_prompt"] = turnaround.get("turnaround_prompt", "")

    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2)

    # Update main SQLite state to step_2_complete
    await update_state(project_uuid, ProjectState.STEP_2_COMPLETE)

    # Update sub-step state in state.json
    state_json_path = os.path.join(project_dir, ".conduit", "state.json")
    if os.path.exists(state_json_path):
        with open(state_json_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
        state_data["step_2_call_2_complete"] = True
        with open(state_json_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

    return CharacterPromptsList(**existing_data)
