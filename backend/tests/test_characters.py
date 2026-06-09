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
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "A brave knight.",
                                            },
                                            {
                                                "name": "Bob",
                                                "type": "creature",
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

        # Assert prompt contains script content (user message)
        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["messages"][0]["role"] == "system"
        assert "character extraction engine" in body["messages"][0]["content"]
        prompt = body["messages"][1]["content"]
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
        assert "AI request failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_extract_characters_authentication_error(async_client, cleanup_projects, created_project):
    """Fireworks API authentication error returns 502."""
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
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/extract"
        )
        assert response.status_code == 502
        assert "AI service authentication failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_extract_characters_rate_limit_error(async_client, cleanup_projects, created_project):
    """Fireworks API rate limit error returns 429."""
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
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/extract"
        )
        assert response.status_code == 429
        assert "AI service rate limited, retry shortly" in response.json()["detail"]


@pytest.mark.asyncio
async def test_call2_two_versions(async_client, cleanup_projects, created_project):
    """Generate prompts for versioned characters — each version gets front + turnaround."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    characters_path = os.path.join(project_dir, "characters.json")

    shared_anchor = "Oval face, strong jawline, hazel eyes, dark wavy hair"
    versioned_characters = {
        "characters": [
            {
                "name": "Hero (young)",
                "base_name": "Hero",
                "version_label": "young",
                "version_index": 0,
                "appears_from": "",
                "type": "speaking",
                "importance": "major",
                "description": "A young hero in simple leather armor.",
                "identity_anchor": shared_anchor,
            },
            {
                "name": "Hero (adult)",
                "base_name": "Hero",
                "version_label": "adult",
                "version_index": 1,
                "appears_from": "After the time skip",
                "type": "speaking",
                "importance": "major",
                "description": "An older hero in ornate plate armor.",
                "identity_anchor": shared_anchor,
            },
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(versioned_characters, f)

    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
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
                                                "name": "Hero (young)",
                                                "front_profile_prompt": f"Front profile young hero, {shared_anchor}, leather armor.",
                                            },
                                            {
                                                "name": "Hero (adult)",
                                                "front_profile_prompt": f"Front profile adult hero, {shared_anchor}, plate armor.",
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
        else:
            return httpx.Response(
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
                                                "name": "Hero (young)",
                                                "turnaround_prompt": f"Turnaround young hero, {shared_anchor}, leather armor.",
                                            },
                                            {
                                                "name": "Hero (adult)",
                                                "turnaround_prompt": f"Turnaround adult hero, {shared_anchor}, plate armor.",
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

    with respx.mock:
        route = respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            side_effect=side_effect
        )

        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/prompts"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "characters" in data
        assert len(data["characters"]) == 2

        for char in data["characters"]:
            assert "front_profile_prompt" in char
            assert "turnaround_prompt" in char
            assert shared_anchor in char["front_profile_prompt"]
            assert shared_anchor in char["turnaround_prompt"]

        assert route.call_count == 2

    # Assert characters.json updated
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["characters"][0]["front_profile_prompt"].startswith("Front profile young hero")
    assert saved["characters"][1]["front_profile_prompt"].startswith("Front profile adult hero")
    assert saved["characters"][0]["turnaround_prompt"].startswith("Turnaround young hero")
    assert saved["characters"][1]["turnaround_prompt"].startswith("Turnaround adult hero")

    # Assert sub-step state updated
    state_json_path = os.path.join(conduit_dir, "state.json")
    with open(state_json_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_2_call_2_complete") is True


@pytest.mark.asyncio
async def test_builders_inject_anchor():
    """Unit test: prompt builders include identity_anchor and version_label in system prompt."""
    from services.prompts import build_front_profile_messages, build_turnaround_messages, get_style

    style = get_style("secret_level")
    characters = [
        {
            "name": "Hero (young)",
            "base_name": "Hero",
            "version_label": "young",
            "version_index": 0,
            "appears_from": "",
            "type": "speaking",
            "importance": "major",
            "description": "A young hero.",
            "identity_anchor": "Oval face, hazel eyes, dark wavy hair",
        }
    ]

    front_messages = build_front_profile_messages(characters, style)
    turnaround_messages = build_turnaround_messages(characters, style)

    assert front_messages[0]["role"] == "system"
    assert turnaround_messages[0]["role"] == "system"

    front_system = front_messages[0]["content"]
    turnaround_system = turnaround_messages[0]["content"]

    assert "identity_anchor" in front_system
    assert "version_label" in front_system
    assert "identity_anchor" in turnaround_system
    assert "version_label" in turnaround_system

    # User message should contain the character data
    assert front_messages[1]["role"] == "user"
    assert turnaround_messages[1]["role"] == "user"
    user_front = front_messages[1]["content"]
    assert "Hero (young)" in user_front
    assert "young" in user_front
    assert "Oval face, hazel eyes, dark wavy hair" in user_front


@pytest.mark.asyncio
async def test_call2_missing_version(async_client, cleanup_projects, created_project):
    """Turnaround omits one version → merge guard raises 502 and characters.json is NOT updated."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    versioned_characters = {
        "characters": [
            {
                "name": "Hero (young)",
                "base_name": "Hero",
                "version_label": "young",
                "version_index": 0,
                "appears_from": "",
                "type": "speaking",
                "importance": "major",
                "description": "A young hero.",
                "identity_anchor": "Oval face, hazel eyes",
            },
            {
                "name": "Hero (adult)",
                "base_name": "Hero",
                "version_label": "adult",
                "version_index": 1,
                "appears_from": "After the time skip",
                "type": "speaking",
                "importance": "major",
                "description": "An older hero.",
                "identity_anchor": "Oval face, hazel eyes",
            },
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(versioned_characters, f)

    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Front profile for both versions
            return httpx.Response(
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
                                                "name": "Hero (young)",
                                                "front_profile_prompt": "Front profile young hero.",
                                            },
                                            {
                                                "name": "Hero (adult)",
                                                "front_profile_prompt": "Front profile adult hero.",
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
        else:
            # Turnaround omits Hero (adult)
            return httpx.Response(
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
                                                "name": "Hero (young)",
                                                "turnaround_prompt": "Turnaround young hero.",
                                            }
                                            # Hero (adult) is missing
                                        ]
                                    }
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            side_effect=side_effect
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/prompts"
        )
        assert response.status_code == 502
        assert "AI returned incomplete character prompts" in response.json()["detail"]

    # Assert characters.json is preserved (no prompts written)
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert "front_profile_prompt" not in saved["characters"][0]
    assert "turnaround_prompt" not in saved["characters"][0]
    assert "front_profile_prompt" not in saved["characters"][1]
    assert "turnaround_prompt" not in saved["characters"][1]
    assert saved["characters"][0]["name"] == "Hero (young)"
    assert saved["characters"][1]["name"] == "Hero (adult)"


@pytest.mark.asyncio
async def test_extract_invalid_enum_returns_502(async_client, cleanup_projects, created_project):
    """AI returning an invalid enum value is rejected and characters.json is NOT written."""
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
                                                "type": "protagonist",  # invalid enum
                                                "importance": "major",
                                                "description": "A brave knight.",
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
            f"/api/v1/projects/{project_uuid}/characters/extract"
        )
        assert response.status_code == 502
        assert "AI returned data in an unexpected format" in response.json()["detail"]

    # Validate-before-persist: file must NOT be written
    characters_path = os.path.join(project_dir, "characters.json")
    assert not os.path.exists(characters_path)


@pytest.mark.asyncio
async def test_get_characters_happy_path(async_client, cleanup_projects, created_project):
    """GET /characters returns 200 with character array."""
    project_uuid = created_project["uuid"]
    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")

    data = {
        "characters": [
            {
                "name": "Alice",
                "type": "speaking",
                "importance": "major",
                "description": "Brave knight.",
            }
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    response = await async_client.get(f"/api/v1/projects/{project_uuid}/characters")
    assert response.status_code == 200
    result = response.json()
    assert "characters" in result
    assert len(result["characters"]) == 1
    assert result["characters"][0]["name"] == "Alice"
    assert result["characters"][0]["type"] == "speaking"
    assert result["characters"][0]["importance"] == "major"
    assert result["characters"][0]["description"] == "Brave knight."


@pytest.mark.asyncio
async def test_get_characters_not_found(async_client, cleanup_projects, created_project):
    """GET /characters for non-existent project returns 404."""
    project_uuid = created_project["uuid"]
    response = await async_client.get(f"/api/v1/projects/{project_uuid}/characters")
    assert response.status_code == 404
    assert "characters.json not found" in response.json()["detail"]


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
                "type": "speaking",
                "importance": "major",
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
                "type": "speaking",
                "importance": "major",
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
                "type": "speaking",
                "importance": "major",
                "description": "A brave knight with silver armor.",
            },
            {
                "name": "Bob",
                "type": "creature",
                "importance": "minor",
                "description": "A cunning thief with a dark cloak.",
            },
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial_characters, f)

    # Two-batch side_effect: first call = front profiles, second call = turnarounds
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
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
                                            },
                                            {
                                                "name": "Bob",
                                                "front_profile_prompt": "Front profile of Bob, a cunning thief with a dark cloak.",
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
        else:
            return httpx.Response(
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
                                                "turnaround_prompt": "360 view of Alice, a brave knight with silver armor.",
                                            },
                                            {
                                                "name": "Bob",
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

    with respx.mock:
        route = respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            side_effect=side_effect
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

        # Assert exactly 2 calls were made
        assert route.call_count == 2

        # Assert prompt contains character descriptions (user message of last call)
        request = route.calls.last.request
        body = json.loads(request.content)
        user_prompt = body["messages"][1]["content"]
        assert "Alice" in user_prompt
        assert "Bob" in user_prompt
        assert "brave knight" in user_prompt
        assert "cunning thief" in user_prompt

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
                "type": "speaking",
                "importance": "major",
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
        assert "AI request failed" in response.json()["detail"]

    # Assert characters.json is preserved (extraction data not lost)
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert "front_profile_prompt" not in saved["characters"][0]
    assert "turnaround_prompt" not in saved["characters"][0]
    assert saved["characters"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_generate_prompts_name_mismatch_returns_502(async_client, cleanup_projects, created_project):
    """Turnaround omits a character → merge guard raises 502 and characters.json is NOT updated."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    initial_characters = {
        "characters": [
            {
                "name": "Alice",
                "type": "speaking",
                "importance": "major",
                "description": "A brave knight.",
            },
            {
                "name": "Bob",
                "type": "creature",
                "importance": "minor",
                "description": "A cunning thief.",
            },
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial_characters, f)

    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Front profile for both characters
            return httpx.Response(
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
                                                "front_profile_prompt": "Front profile of Alice.",
                                            },
                                            {
                                                "name": "Bob",
                                                "front_profile_prompt": "Front profile of Bob.",
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
        else:
            # Turnaround omits Bob
            return httpx.Response(
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
                                                "turnaround_prompt": "360 view of Alice.",
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

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            side_effect=side_effect
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/prompts"
        )
        assert response.status_code == 502
        assert "AI returned incomplete character prompts" in response.json()["detail"]

    # Assert characters.json is preserved (no prompts written)
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert "front_profile_prompt" not in saved["characters"][0]
    assert "turnaround_prompt" not in saved["characters"][0]
    assert "front_profile_prompt" not in saved["characters"][1]
    assert "turnaround_prompt" not in saved["characters"][1]
    assert saved["characters"][0]["name"] == "Alice"
    assert saved["characters"][1]["name"] == "Bob"


@pytest.mark.asyncio
async def test_generate_prompts_authentication_error(async_client, cleanup_projects, created_project):
    """Fireworks API authentication error returns 502."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    initial_characters = {
        "characters": [
            {
                "name": "Alice",
                "type": "speaking",
                "importance": "major",
                "description": "A brave knight.",
            }
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial_characters, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/prompts"
        )
        assert response.status_code == 502
        assert "AI service authentication failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_prompts_rate_limit_error(async_client, cleanup_projects, created_project):
    """Fireworks API rate limit error returns 429."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    initial_characters = {
        "characters": [
            {
                "name": "Alice",
                "type": "speaking",
                "importance": "major",
                "description": "A brave knight.",
            }
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(initial_characters, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        response = await async_client.post(
            f"/api/v1/projects/{project_uuid}/characters/prompts"
        )
        assert response.status_code == 429
        assert "AI service rate limited, retry shortly" in response.json()["detail"]


@pytest.mark.asyncio
async def test_put_characters_invalidates_downstream(async_client, cleanup_projects, created_project):
    """PUT characters resets downstream state and deletes segments.json."""
    project_uuid = created_project["uuid"]

    # Advance to step_3_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/3")

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")

    # Create segments.json (downstream artifact)
    segments_path = os.path.join(conduit_dir, "segments.json")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello", "start_time": 0.0, "end_time": 1.0, "duration": 1.0}
        ]
    }
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments, f)

    # Set downstream sub-step states
    state_path = os.path.join(conduit_dir, "state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    state_data["step_2_call_2_complete"] = True
    state_data["step_3_pass_1_complete"] = True
    state_data["step_3_pass_2_complete"] = True
    state_data["step_4_images_uploaded"] = True
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f)

    # Create characters.json
    characters_path = os.path.join(project_dir, "characters.json")
    characters = {
        "characters": [
            {"name": "Alice", "type": "speaking", "importance": "major", "description": "A brave knight."}
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(characters, f)

    # PUT characters
    updated = {
        "characters": [
            {"name": "Alice", "type": "speaking", "importance": "major", "description": "A very brave knight."}
        ]
    }
    response = await async_client.put(f"/api/v1/projects/{project_uuid}/characters", json=updated)
    assert response.status_code == 200
    data = response.json()
    assert data["characters"][0]["description"] == "A very brave knight."

    # Assert DB state reset to step_1_complete
    db = await models.database.get_db()
    try:
        cursor = await db.execute("SELECT state FROM projects WHERE uuid = ?", (project_uuid,))
        row = await cursor.fetchone()
    finally:
        await db.close()
    assert row[0] == "step_1_complete"

    # Assert segments.json deleted
    assert not os.path.exists(segments_path)

    # Assert downstream sub-steps cleared
    with open(state_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_2_call_2_complete") is None
    assert state_data.get("step_3_pass_1_complete") is None
    assert state_data.get("step_3_pass_2_complete") is None
    assert state_data.get("step_4_images_uploaded") is None


@pytest.mark.asyncio
async def test_load_pre_version_characters(async_client, cleanup_projects, created_project):
    """GET /characters loads pre-version characters.json without ValidationError."""
    project_uuid = created_project["uuid"]
    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")

    pre_version = {
        "characters": [
            {"name": "Alice", "type": "speaking", "importance": "major", "description": "A brave knight."}
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(pre_version, f)

    response = await async_client.get(f"/api/v1/projects/{project_uuid}/characters")
    assert response.status_code == 200
    data = response.json()
    assert len(data["characters"]) == 1
    char = data["characters"][0]
    assert char["name"] == "Alice"
    assert char["type"] == "speaking"
    assert char["importance"] == "major"
    assert char["description"] == "A brave knight."
    assert char["version_label"] == "default"
    assert char["base_name"] == "Alice"
    assert char["version_index"] == 0
    assert char["appears_from"] == ""
    assert char["identity_anchor"] == ""


@pytest.mark.asyncio
async def test_call2_with_pre_version_characters(async_client, cleanup_projects, created_project):
    """Mock Call 2 with pre-version characters.json succeeds and defaults applied."""
    project_uuid = created_project["uuid"]

    # Advance to step_1_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")

    pre_version = {
        "characters": [
            {"name": "Alice", "type": "speaking", "importance": "major", "description": "A brave knight."}
        ]
    }
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(pre_version, f)

    def side_effect(request):
        return httpx.Response(
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
                            "content": json.dumps({
                                "characters": [
                                    {
                                        "name": "Alice",
                                        "front_profile_prompt": "Front profile of Alice.",
                                        "turnaround_prompt": "360 view of Alice.",
                                    }
                                ]
                            }),
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(side_effect=side_effect)
        response = await async_client.post(f"/api/v1/projects/{project_uuid}/characters/prompts")
        assert response.status_code == 200
        data = response.json()
        assert data["characters"][0]["name"] == "Alice"
        assert data["characters"][0]["front_profile_prompt"] == "Front profile of Alice."
        assert data["characters"][0]["turnaround_prompt"] == "360 view of Alice."

    # Verify persisted file has prompts
    with open(characters_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["characters"][0]["front_profile_prompt"] == "Front profile of Alice."
    assert saved["characters"][0]["turnaround_prompt"] == "360 view of Alice."

    # GET /characters to verify defaults applied
    get_resp = await async_client.get(f"/api/v1/projects/{project_uuid}/characters")
    assert get_resp.status_code == 200
    char = get_resp.json()["characters"][0]
    assert char["version_label"] == "default"
    assert char["base_name"] == "Alice"
    assert char["version_index"] == 0


@pytest.mark.asyncio
async def test_extract_characters_max_tokens_16000(async_client, cleanup_projects, created_project):
    """POST characters/extract sends max_tokens=16000 to Fireworks (truncation guard)."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    with open(os.path.join(conduit_dir, "source_of_truth_script.txt"), "w", encoding="utf-8") as f:
        f.write("Alice is a brave knight.")

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
                                                "type": "speaking",
                                                "importance": "major",
                                                "description": "A brave knight.",
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

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/characters/extract")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["max_tokens"] == 16000


@pytest.mark.asyncio
async def test_timeline_max_tokens_16000(async_client, cleanup_projects, created_project):
    """POST characters/timeline sends max_tokens=16000 to Fireworks (truncation guard).

    The timeline endpoint requires BOTH characters.json AND source_of_truth_script.txt
    (else 400 'No script found' before the AI call), so both are written here.
    """
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    with open(os.path.join(conduit_dir, "source_of_truth_script.txt"), "w", encoding="utf-8") as f:
        f.write("Alice is a brave knight who grows old over the years.")

    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(
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
            },
            f,
        )

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

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/characters/timeline")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["max_tokens"] == 16000


@pytest.mark.asyncio
async def test_generate_prompts_max_tokens_16000(async_client, cleanup_projects, created_project):
    """POST characters/prompts sends max_tokens=16000 on BOTH Call-2 requests (front + turnaround)."""
    project_uuid = created_project["uuid"]
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200

    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "characters": [
                    {
                        "name": "Alice",
                        "type": "speaking",
                        "importance": "major",
                        "description": "A brave knight with silver armor.",
                    }
                ]
            },
            f,
        )

    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        field = "front_profile_prompt" if call_count == 1 else "turnaround_prompt"
        return httpx.Response(
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
                                {"characters": [{"name": "Alice", field: "A prompt for Alice."}]}
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with respx.mock:
        route = respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            side_effect=side_effect
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/characters/prompts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        # Call 2 fires exactly two requests (front + turnaround); both must be budgeted at 16000.
        assert route.call_count == 2
        assert all(
            json.loads(c.request.content)["max_tokens"] == 16000 for c in route.calls
        )


@pytest.mark.asyncio
async def test_get_characters_preserves_prompt_fields(async_client, cleanup_projects, created_project):
    """Issue 3: GET /characters must return persisted front_profile_prompt /
    turnaround_prompt (not strip them via response_model)."""
    project_uuid = created_project["uuid"]
    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump({"characters": [{
            "name": "Alice",
            "type": "speaking",
            "importance": "major",
            "description": "A brave knight.",
            "base_name": "Alice",
            "version_label": "default",
            "version_index": 0,
            "front_profile_prompt": "Front profile of Alice.",
            "turnaround_prompt": "360 view of Alice.",
        }]}, f)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/characters")
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text}"
    char = resp.json()["characters"][0]
    assert char["front_profile_prompt"] == "Front profile of Alice."
    assert char["turnaround_prompt"] == "360 view of Alice."


@pytest.mark.asyncio
async def test_get_characters_legacy_backfills_base_name(async_client, cleanup_projects, created_project):
    """Issue 3 back-compat: a legacy characters.json with no base_name/prompts
    still returns 200 with base_name backfilled from name."""
    project_uuid = created_project["uuid"]
    project_dir = os.path.join(projects_module.PROJECTS_BASE_DIR, project_uuid)
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump({"characters": [{
            "name": "Bob",
            "type": "creature",
            "importance": "minor",
            "description": "A thief.",
        }]}, f)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/characters")
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text}"
    char = resp.json()["characters"][0]
    assert char["base_name"] == "Bob"
