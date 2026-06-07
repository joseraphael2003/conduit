import os
import json
from datetime import datetime, timezone
from fastapi import HTTPException, status
from models.database import get_db
from models.state import ProjectState
from config import PROJECTS_BASE_DIR

STATE_ORDER = [
    ProjectState.CREATED,
    ProjectState.STEP_1_COMPLETE,
    ProjectState.STEP_2_COMPLETE,
    ProjectState.STEP_3_COMPLETE,
    ProjectState.STEP_4_COMPLETE,
    ProjectState.STEP_5_COMPLETE,
]

SUB_STEP_KEYS = [
    "step_2_call_1_complete",
    "step_2_call_2_complete",
    "step_3_pass_1_complete",
    "step_3_pass_2_complete",
    "step_4_images_uploaded",
]


def get_state_index(state: ProjectState) -> int:
    try:
        return STATE_ORDER.index(state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state: {state}",
        )


async def get_state(uuid: str) -> ProjectState:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT state FROM projects WHERE uuid = ?", (uuid,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return ProjectState(row[0])


async def update_state(uuid: str, new_state: ProjectState) -> ProjectState:
    current_state = await get_state(uuid)
    current_idx = get_state_index(current_state)
    new_idx = get_state_index(new_state)

    # No-op if same state
    if new_idx == current_idx:
        return current_state

    # Only allow forward by exactly 1 step
    if new_idx != current_idx + 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prerequisite step not met",
        )

    db = await get_db()
    try:
        await db.execute(
            "UPDATE projects SET state = ?, updated_at = CURRENT_TIMESTAMP WHERE uuid = ?",
            (new_state.value, uuid),
        )
        await db.commit()
    finally:
        await db.close()

    # Update state.json
    state_json_path = os.path.join(
        PROJECTS_BASE_DIR, uuid, ".conduit", "state.json"
    )
    if os.path.exists(state_json_path):
        with open(state_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["state"] = new_state.value
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(state_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    return new_state


def _get_state_json_path(uuid: str) -> str:
    return os.path.join(PROJECTS_BASE_DIR, uuid, ".conduit", "state.json")


def get_sub_step_state(uuid: str) -> dict:
    """Read sub-step progress from state.json."""
    state_json_path = _get_state_json_path(uuid)
    if not os.path.exists(state_json_path):
        return {}
    with open(state_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: data.get(k) for k in SUB_STEP_KEYS if k in data}


def set_sub_step_state(uuid: str, key: str, value) -> None:
    """Update sub-step progress in state.json."""
    state_json_path = _get_state_json_path(uuid)
    if not os.path.exists(state_json_path):
        return
    with open(state_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data[key] = value
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(state_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_style_id(uuid: str) -> str:
    """Read style_id from state.json, defaulting to secret_level."""
    state_json_path = _get_state_json_path(uuid)
    if not os.path.exists(state_json_path):
        return "secret_level"
    with open(state_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("style_id", "secret_level")


def _delete_downstream_files(project_dir: str, edited_step: int) -> None:
    """Delete downstream JSON files when invalidating from a step."""
    # Step 1 specific files
    if edited_step <= 1:
        captions_path = os.path.join(project_dir, "captions.srt")
        if os.path.exists(captions_path):
            os.remove(captions_path)

    # Step 2: delete segments.json
    if edited_step <= 2:
        segments_path = os.path.join(project_dir, ".conduit", "segments.json")
        if os.path.exists(segments_path):
            os.remove(segments_path)

    # Always preserve images/ and .conduit/ directories


def _clear_sub_step_state(data: dict, edited_step: int) -> dict:
    """Clear downstream sub-step state based on the edited step."""
    if edited_step == 1:
        for key in SUB_STEP_KEYS:
            data.pop(key, None)
    elif edited_step == 2:
        data.pop("step_3_pass_1_complete", None)
        data.pop("step_3_pass_2_complete", None)
        data.pop("step_4_images_uploaded", None)
    elif edited_step == 3:
        data.pop("step_4_images_uploaded", None)
    elif edited_step == 4:
        # Clear step 5 sub-steps (none defined yet)
        pass
    return data


async def invalidate_downstream(uuid: str, edited_step: int) -> ProjectState:
    if edited_step < 1 or edited_step > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid step number",
        )

    # Reset state to step N-1 (e.g., step 2 -> step_1_complete)
    new_state = STATE_ORDER[edited_step - 1]

    db = await get_db()
    try:
        await db.execute(
            "UPDATE projects SET state = ?, updated_at = CURRENT_TIMESTAMP WHERE uuid = ?",
            (new_state.value, uuid),
        )
        await db.commit()
    finally:
        await db.close()

    # Update state.json
    state_json_path = os.path.join(
        PROJECTS_BASE_DIR, uuid, ".conduit", "state.json"
    )
    if os.path.exists(state_json_path):
        with open(state_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["state"] = new_state.value
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data = _clear_sub_step_state(data, edited_step)
        with open(state_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # Delete downstream files
    project_dir = os.path.join(PROJECTS_BASE_DIR, uuid)
    if os.path.exists(project_dir):
        _delete_downstream_files(project_dir, edited_step)

    return new_state
