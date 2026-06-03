import os
import json
import pytest
import httpx
import respx
import routers.projects as projects_module
import models.database


@pytest.mark.asyncio
async def test_extract_characters_happy_path(async_client, cleanup_projects, created_project):
    """Extract characters from script and verify state persistence."""
    project_uuid = created_project["uuid"]

    # Advance state to step_1_complete
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    # Write source_of_truth_script.txt
    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    script_path = os.path.join(conduit_dir, "source_of_truth_script.txt")
    script_content = "Alice is a brave knight. Bob is a cunning thief."
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # Mock Fireworks AI response
    with respx.mock:
        route = respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
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
                                                "type": "protagonist",
                                                "importance": "main",
                                                "description": "A brave knight.",
                                            },
                                            {
                                                "name": "Bob",
                                                "type": "antagonist",
                                                "importance": "minor",
                                                "description": "A cunning thief.",
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
            f"/api/v1/projects/{project_uuid}/characters/extract"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "characters" in data
        assert len(data["characters"]) == 2
        for char in data["characters"]:
            assert "name" in char
            assert "type" in char
            assert "importance" in char
            assert "description" in char

        # Assert prompt contains script content
        request = route.calls.last.request
        body = json.loads(request.content)
        prompt = body["messages"][0]["content"]
        assert script_content in prompt, "Prompt should contain script content"

    # Assert characters.json saved
    characters_path = os.path.join(project_dir, "characters.json")
    assert os.path.exists(characters_path)
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved == data

    # Assert sub-step state updated
    state_json_path = os.path.join(conduit_dir, "state.json")
    with open(state_json_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_2_call_1_complete") is True

    # Assert main SQLite state remains step_1_complete
    db = await models.database.get_db()
    try:
        cursor = await db.execute(
            "SELECT state FROM projects WHERE uuid = ?", (project_uuid,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    assert row[0] == "step_1_complete"


@pytest.mark.asyncio
async def test_extract_characters_missing_script(async_client, cleanup_projects, created_project):
    """Missing script returns 400."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/characters/extract"
    )
    assert response.status_code == 400
    assert "No script found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_extract_characters_prerequisite_not_met(async_client, cleanup_projects, created_project):
    """State is 'created' → prerequisite not met returns 409."""
    project_uuid = created_project["uuid"]
    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/characters/extract"
    )
    assert response.status_code == 409
    assert "Prerequisite step not met" in response.json()["detail"]


@pytest.mark.asyncio
async def test_extract_characters_fireworks_failure(async_client, cleanup_projects, created_project):
    """Fireworks API failure after retries returns 502."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    script_path = os.path.join(conduit_dir, "source_of_truth_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("Some script content")

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/extract"
        )
        assert response.status_code == 502
        assert "Character extraction failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_characters(async_client, cleanup_projects, created_project):
    """PUT characters persists edited list and returns updated data."""
    project_uuid = created_project["uuid"]
    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")

    initial = {
        "characters": [
            {
                "name": "Alice",
                "type": "protagonist",
                "importance": "main",
                "description": "Brave knight.",
            }
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    updated = {
        "characters": [
            {
                "name": "Alice",
                "type": "protagonist",
                "importance": "main",
                "description": "A very brave knight.",
            }
        ]
    }
    response = await async_client.put(
        f"/api/v1/projects/{project_uuid}/characters", json=updated
    )
    assert response.status_code == 200
    data = response.json()
    assert data["characters"][0]["description"] == "A very brave knight."

    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved == data


@pytest.mark.asyncio
async def test_generate_prompts_happy_path(async_client, cleanup_projects, created_project):
    """Generate character prompts and verify state persistence."""
    project_uuid = created_project["uuid"]

    # Advance state to step_1_complete
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    # Write characters.json (simulating Call 1 completion)
    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    characters_path = os.path.join(project_dir, "characters.json")
    initial_characters = {
        "characters": [
            {
                "name": "Alice",
                "type": "protagonist",
                "importance": "main",
                "description": "A brave knight with silver armor.",
            },
            {
                "name": "Bob",
                "type": "antagonist",
                "importance": "minor",
                "description": "A cunning thief with a dark cloak.",
            },
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial_characters, f)

    # Mock Fireworks AI response
    with respx.mock:
        route = respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
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
                                                "front_profile_prompt": "Front profile of Alice, a brave knight with silver armor.",
                                                "turnaround_prompt": "360 view of Alice, a brave knight with silver armor.",
                                            },
                                            {
                                                "name": "Bob",
                                                "front_profile_prompt": "Front profile of Bob, a cunning thief with a dark cloak.",
                                                "turnaround_prompt": "360 view of Bob, a cunning thief with a dark cloak.",
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
            f"/api/v1/projects/{project_uuid}/characters/prompts"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "characters" in data
        assert len(data["characters"]) == 2
        for char in data["characters"]:
            assert "name" in char
            assert "front_profile_prompt" in char
            assert "turnaround_prompt" in char

        # Assert prompt contains character descriptions
        request = route.calls.last.request
        body = json.loads(request.content)
        prompt = body["messages"][0]["content"]
        assert "Alice" in prompt
        assert "Bob" in prompt
        assert "brave knight" in prompt
        assert "cunning thief" in prompt

    # Assert characters.json updated with prompts
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert "front_profile_prompt" in saved["characters"][0]
    assert "turnaround_prompt" in saved["characters"][0]
    assert saved["characters"][0]["front_profile_prompt"] == "Front profile of Alice, a brave knight with silver armor."
    assert saved["characters"][1]["turnaround_prompt"] == "360 view of Bob, a cunning thief with a dark cloak."

    # Assert sub-step state updated
    state_json_path = os.path.join(conduit_dir, "state.json")
    with open(state_json_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_2_call_2_complete") is True

    # Assert main SQLite state updated to step_2_complete
    db = await models.database.get_db()
    try:
        cursor = await db.execute(
            "SELECT state FROM projects WHERE uuid = ?", (project_uuid,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    assert row[0] == "step_2_complete"


@pytest.mark.asyncio
async def test_generate_prompts_missing_characters(async_client, cleanup_projects, created_project):
    """Missing characters.json returns 409."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/characters/prompts"
    )
    assert response.status_code == 409
    assert "Character extraction not completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_prompts_fireworks_failure(async_client, cleanup_projects, created_project):
    """Fireworks API failure after retries returns 502."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    initial_characters = {
        "characters": [
            {
                "name": "Alice",
                "type": "protagonist",
                "importance": "main",
                "description": "A brave knight.",
            }
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial_characters, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/prompts"
        )
        assert response.status_code == 502
        assert "Prompt generation failed" in response.json()["detail"]

    # Assert characters.json is preserved (extraction data not lost)
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert "front_profile_prompt" not in saved["characters"][0]
    assert "turnaround_prompt" not in saved["characters"][0]
    assert saved["characters"][0]["name"] == "Alice"
