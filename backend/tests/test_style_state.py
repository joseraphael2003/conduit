import os
import json
import pytest

import services.state as state_module


@pytest.mark.asyncio
async def test_create_project_persists_style_id(async_client, cleanup_projects, temp_projects_dir):
    """Creating a project writes style_id = secret_level to state.json."""
    response = await async_client.post("/api/v1/projects", json={"name": "Style Test"})
    assert response.status_code == 201
    project_uuid = response.json()["uuid"]

    state_json_path = os.path.join(temp_projects_dir, project_uuid, ".conduit", "state.json")
    assert os.path.exists(state_json_path)

    with open(state_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("style_id") == "secret_level"


@pytest.mark.asyncio
async def test_get_style_id_defaults_for_missing_key(temp_projects_dir):
    """get_style_id returns secret_level when state.json lacks the key."""
    # Create a minimal project directory with an old-style state.json
    project_uuid = "00000000-0000-0000-0000-000000000001"
    project_dir = os.path.join(temp_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    os.makedirs(conduit_dir, exist_ok=True)

    old_state = {"uuid": project_uuid, "state": "created"}
    state_json_path = os.path.join(conduit_dir, "state.json")
    with open(state_json_path, "w", encoding="utf-8") as f:
        json.dump(old_state, f, indent=2)

    assert state_module.get_style_id(project_uuid) == "secret_level"
