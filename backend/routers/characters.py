import logging
import os
import json
from typing import List

from fastapi import APIRouter, HTTPException, status
from openai._exceptions import AuthenticationError, RateLimitError, APIError
from pydantic import BaseModel

from services.fireworks import FireworksClient
from services.state import get_state, update_state
from models.state import ProjectState
import routers.projects as _projects_module

characters_router = APIRouter()


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
    if isinstance(exc, APIError):
        logging.error("AI request failed", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI request failed",
        ) from exc
    raise exc


class CharacterDescription(BaseModel):
    name: str
    type: str
    importance: str
    description: str


class CharacterList(BaseModel):
    characters: List[CharacterDescription]


class CharacterPrompts(BaseModel):
    name: str
    front_profile_prompt: str
    turnaround_prompt: str


class CharacterPromptsList(BaseModel):
    characters: List[CharacterPrompts]


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

    # Build extraction prompt
    prompt = (
        "Extract all characters from the following script. "
        "For each character, provide: name, type (e.g., protagonist, antagonist, supporting), "
        "importance (e.g., main, minor, background), and a brief description. "
        "Return ONLY valid JSON matching the requested schema.\n\n"
        f"{script_content}"
    )

    # Call Fireworks AI
    client = FireworksClient()
    try:
        result = await client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            json_schema=CharacterList,
        )
    except (AuthenticationError, RateLimitError, APIError) as exc:
        _handle_fireworks_error(exc)

    # Save extraction result to characters.json
    project_dir = os.path.join(_projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Update sub-step state in state.json
    state_json_path = os.path.join(project_dir, ".conduit", "state.json")
    if os.path.exists(state_json_path):
        with open(state_json_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
        state_data["step_2_call_1_complete"] = True
        with open(state_json_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

    return CharacterList(**result)


@characters_router.get(
    "/projects/{project_uuid}/characters",
    response_model=CharacterList,
)
async def get_characters(project_uuid: str):
    """Retrieve the project's character list from characters.json."""
    project_dir = os.path.join(_projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    if not os.path.exists(characters_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="characters.json not found",
        )
    with open(characters_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CharacterList(**data)


@characters_router.put(
    "/projects/{project_uuid}/characters",
    response_model=CharacterList,
)
async def update_characters(project_uuid: str, characters: CharacterList):
    """Accept an edited character list and persist it to characters.json."""
    project_dir = os.path.join(_projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(characters.model_dump(), f, indent=2)
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

    # Build prompt generation prompt
    prompt_lines = [
        "For each character below, generate two prompts:",
        "1. front_profile_prompt: A detailed description of the character's face from the front, suitable for generating a front-profile image.",
        "2. turnaround_prompt: A detailed description of the character's appearance (clothing, features, build) from all angles, suitable for a 360-degree turnaround.",
        "Return ONLY valid JSON matching the requested schema.",
        "",
        "Characters:",
    ]
    for char in characters:
        name = char.get("name", "Unknown")
        description = char.get("description", "")
        char_type = char.get("type", "")
        importance = char.get("importance", "")
        prompt_lines.append(f"- {name} ({importance} {char_type}): {description}")

    prompt = "\n".join(prompt_lines)

    # Call Fireworks AI
    client = FireworksClient()
    try:
        result = await client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            json_schema=CharacterPromptsList,
        )
    except (AuthenticationError, RateLimitError, APIError) as exc:
        _handle_fireworks_error(exc)

    # Merge prompts back into existing characters.json
    prompts_data = result
    for char in characters:
        for prompt_entry in prompts_data.get("characters", []):
            if prompt_entry.get("name") == char.get("name"):
                char["front_profile_prompt"] = prompt_entry.get("front_profile_prompt", "")
                char["turnaround_prompt"] = prompt_entry.get("turnaround_prompt", "")
                break

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

    return CharacterPromptsList(**prompts_data)
