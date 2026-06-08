import os
import json
import pytest
import httpx
import respx
import routers.projects as projects_module
import models.database


async def _advance_to_step_1(async_client, project_uuid: str) -> None:
    """Advance project to step 1 and write source script."""
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    script_path = os.path.join(conduit_dir, "source_of_truth_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("Alice is a brave knight. Bob is a cunning thief.")


@pytest.mark.asyncio
async def test_timeline_happy(async_client, cleanup_projects, created_project):
    """Timeline expands a single character into two versions with shared base_name."""
    project_uuid = created_project["uuid"]
    await _advance_to_step_1(async_client, project_uuid)

    # Mock Call 1 (extract) — single character with base_name
    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "characters": [
                                            {
                                                "name": "Alice",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "A brave knight.",
                                                "base_name": "Alice",
                                                "version_label": "default",
                                                "version_index": 0,
                                                "identity_anchor": "Silver-armored knight with blue eyes",
                                            }
                                        ]
                                    }
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
        extract_resp = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/extract"
        )
        assert extract_resp.status_code == 200

    # Mock timeline — 2 versions, shared base_name, identical identity_anchor, unique names
    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "characters": [
                                            {
                                                "name": "Alice (Young)",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "A brave young knight.",
                                                "base_name": "Alice",
                                                "version_label": "Young",
                                                "version_index": 0,
                                                "identity_anchor": "Silver-armored knight with blue eyes",
                                                "appears_from": "00:00",
                                            },
                                            {
                                                "name": "Alice (Old)",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "A brave old knight.",
                                                "base_name": "Alice",
                                                "version_label": "Old",
                                                "version_index": 1,
                                                "identity_anchor": "Silver-armored knight with blue eyes",
                                                "appears_from": "05:00",
                                            },
                                        ]
                                    }
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/timeline"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert len(data["characters"]) == 2
        assert data["characters"][0]["base_name"] == "Alice"
        assert data["characters"][1]["base_name"] == "Alice"
        assert data["characters"][0]["identity_anchor"] == "Silver-armored knight with blue eyes"
        assert data["characters"][1]["identity_anchor"] == "Silver-armored knight with blue eyes"
        assert data["characters"][0]["name"] != data["characters"][1]["name"]

    # Assert characters.json saved
    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved["characters"]) == 2

    # Assert sub-step state updated
    state_json_path = os.path.join(project_dir, ".conduit", "state.json")
    with open(state_json_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_2_timeline_complete") is True


@pytest.mark.asyncio
async def test_timeline_409_no_characters(async_client, cleanup_projects, created_project):
    """POST timeline on project with no characters.json returns 409."""
    project_uuid = created_project["uuid"]
    await _advance_to_step_1(async_client, project_uuid)

    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/characters/timeline"
    )
    assert response.status_code == 409
    assert "Character extraction not completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_timeline_502_duplicate_name(async_client, cleanup_projects, created_project):
    """Mock timeline returning duplicate names returns 502."""
    project_uuid = created_project["uuid"]
    await _advance_to_step_1(async_client, project_uuid)

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    initial = {
        "characters": [
            {
                "name": "Alice",
                "type": "speaking",
                "importance": "major",
                "description": "A brave knight.",
                "base_name": "Alice",
            }
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "characters": [
                                            {
                                                "name": "Alice (Young)",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "Young Alice.",
                                                "base_name": "Alice",
                                                "version_label": "Young",
                                                "identity_anchor": "Silver-armored knight",
                                            },
                                            {
                                                "name": "Alice (Young)",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "Duplicate young Alice.",
                                                "base_name": "Alice",
                                                "version_label": "Young",
                                                "identity_anchor": "Silver-armored knight",
                                            },
                                        ]
                                    }
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/timeline"
        )
        assert response.status_code == 502
        assert "Character timeline contains duplicate names" in response.json()["detail"]

    # Assert characters.json is NOT updated
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved["characters"]) == 1


@pytest.mark.asyncio
async def test_timeline_502_missing_person(async_client, cleanup_projects, created_project):
    """Mock timeline drops a person → 502."""
    project_uuid = created_project["uuid"]
    await _advance_to_step_1(async_client, project_uuid)

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    initial = {
        "characters": [
            {
                "name": "Alice",
                "type": "speaking",
                "importance": "major",
                "description": "A brave knight.",
                "base_name": "Alice",
            },
            {
                "name": "Bob",
                "type": "creature",
                "importance": "minor",
                "description": "A cunning thief.",
                "base_name": "Bob",
            },
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "characters": [
                                            {
                                                "name": "Alice",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "A brave knight.",
                                                "base_name": "Alice",
                                                "version_label": "default",
                                                "identity_anchor": "Silver-armored knight",
                                            }
                                            # Bob is missing
                                        ]
                                    }
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/timeline"
        )
        assert response.status_code == 502
        assert "Character timeline missing versions for some characters" in response.json()["detail"]

    # Assert characters.json is preserved
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved["characters"]) == 2
    assert saved["characters"][1]["name"] == "Bob"


@pytest.mark.asyncio
async def test_timeline_502_inconsistent_anchor(async_client, cleanup_projects, created_project):
    """Mock timeline returns inconsistent identity_anchor per base_name → 502."""
    project_uuid = created_project["uuid"]
    await _advance_to_step_1(async_client, project_uuid)

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    initial = {
        "characters": [
            {
                "name": "Alice",
                "type": "speaking",
                "importance": "major",
                "description": "A brave knight.",
                "base_name": "Alice",
            }
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "characters": [
                                            {
                                                "name": "Alice (Young)",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "Young Alice.",
                                                "base_name": "Alice",
                                                "version_label": "Young",
                                                "identity_anchor": "Silver-armored knight",
                                            },
                                            {
                                                "name": "Alice (Old)",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "Old Alice.",
                                                "base_name": "Alice",
                                                "version_label": "Old",
                                                "identity_anchor": "Golden-armored knight",
                                            },
                                        ]
                                    }
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/timeline"
        )
        assert response.status_code == 502
        assert "Inconsistent identity_anchor across versions" in response.json()["detail"]

    # Assert characters.json is preserved
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved["characters"]) == 1


@pytest.mark.asyncio
async def test_timeline_single_version(async_client, cleanup_projects, created_project):
    """Mock timeline returns single version (default label) → 200."""
    project_uuid = created_project["uuid"]
    await _advance_to_step_1(async_client, project_uuid)

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    initial = {
        "characters": [
            {
                "name": "Alice",
                "type": "speaking",
                "importance": "major",
                "description": "A brave knight.",
                "base_name": "Alice",
            }
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-id",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "characters": [
                                            {
                                                "name": "Alice",
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "A brave knight.",
                                                "base_name": "Alice",
                                                "version_label": "default",
                                                "version_index": 0,
                                                "identity_anchor": "Silver-armored knight",
                                            }
                                        ]
                                    }
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/timeline"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["characters"]) == 1
        assert data["characters"][0]["version_label"] == "default"

    # Assert sub-step state updated
    state_json_path = os.path.join(project_dir, ".conduit", "state.json")
    with open(state_json_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_2_timeline_complete") is True

    # Assert characters.json updated
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved["characters"]) == 1
    assert saved["characters"][0]["version_label"] == "default"
