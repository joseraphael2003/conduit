import os
import json
import pytest
import httpx
import respx

import routers.segments as segments_module


@pytest.mark.asyncio
async def test_breakdown_segments(async_client, cleanup_projects, temp_projects_dir):
    """POST /api/v1/projects/{uuid}/segments/breakdown returns 200 with segments."""
    # Create project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Segment Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Advance state to step_2_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    # Create script and words files
    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    script_path = os.path.join(conduit_dir, "source_of_truth_script.txt")
    words_path = os.path.join(conduit_dir, "words.json")

    with open(script_path, "w", encoding="utf-8") as f:
        f.write("Hello world. This is a test.")

    words_data = {
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
            {"word": "This", "start": 1.1, "end": 1.5},
            {"word": "is", "start": 1.6, "end": 1.8},
            {"word": "a", "start": 1.9, "end": 2.0},
            {"word": "test", "start": 2.1, "end": 2.5},
        ]
    }
    with open(words_path, "w", encoding="utf-8") as f:
        json.dump(words_data, f)

    # Mock Fireworks
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
                                "content": json.dumps({
                                    "segments": [
                                        {
                                            "segment_index": 0,
                                            "script_line": "Hello world.",
                                            "start_time": 0.0,
                                            "end_time": 1.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 1,
                                            "script_line": "This is a test.",
                                            "start_time": 1.1,
                                            "end_time": 2.5,
                                            "duration": 1.4,
                                        },
                                    ]
                                }),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/breakdown")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "segments" in data
        assert len(data["segments"]) == 2

        # Assert the prompt contains both script and word timestamps
        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["messages"][0]["role"] == "system"
        assert "video editor" in body["messages"][0]["content"]
        prompt = body["messages"][1]["content"]
        assert "Hello world. This is a test." in prompt
        assert "Hello" in prompt
        assert "world" in prompt

    # Assert segments.json was saved
    segments_path = os.path.join(conduit_dir, "segments.json")
    assert os.path.exists(segments_path)
    with open(segments_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["segments"][0]["script_line"] == "Hello world."

    # Assert state.json updated
    state_path = os.path.join(conduit_dir, "state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_3_pass_1_complete") is True


@pytest.mark.asyncio
async def test_breakdown_missing_files(async_client, cleanup_projects, temp_projects_dir):
    """POST breakdown returns 400 when files are missing."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Missing Files"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/breakdown")
    assert resp.status_code == 400
    assert "Missing source_of_truth_script.txt" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_breakdown_prerequisite_not_met(async_client, cleanup_projects):
    """POST breakdown returns 409 when project is not at step_2_complete."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Prereq Test"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/breakdown")
    assert resp.status_code == 409
    assert "Prerequisites not met" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_breakdown_fireworks_failure(async_client, cleanup_projects, temp_projects_dir):
    """POST breakdown returns 502 when Fireworks API fails."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Fireworks Fail"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    with open(os.path.join(conduit_dir, "source_of_truth_script.txt"), "w", encoding="utf-8") as f:
        f.write("Hello.")
    with open(os.path.join(conduit_dir, "words.json"), "w", encoding="utf-8") as f:
        json.dump({"words": [{"word": "Hello", "start": 0.0, "end": 0.5}]}, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/breakdown")
        assert resp.status_code == 502


@pytest.mark.asyncio
async def test_breakdown_authentication_error(async_client, cleanup_projects, temp_projects_dir):
    """POST breakdown returns 502 on AI authentication error."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Auth Fail"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    with open(os.path.join(conduit_dir, "source_of_truth_script.txt"), "w", encoding="utf-8") as f:
        f.write("Hello.")
    with open(os.path.join(conduit_dir, "words.json"), "w", encoding="utf-8") as f:
        json.dump({"words": [{"word": "Hello", "start": 0.0, "end": 0.5}]}, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/breakdown")
        assert resp.status_code == 502
        assert "AI service authentication failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_breakdown_rate_limit_error(async_client, cleanup_projects, temp_projects_dir):
    """POST breakdown returns 429 on AI rate limit error."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Rate Limit"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    with open(os.path.join(conduit_dir, "source_of_truth_script.txt"), "w", encoding="utf-8") as f:
        f.write("Hello.")
    with open(os.path.join(conduit_dir, "words.json"), "w", encoding="utf-8") as f:
        json.dump({"words": [{"word": "Hello", "start": 0.0, "end": 0.5}]}, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/breakdown")
        assert resp.status_code == 429
        assert "AI service rate limited, retry shortly" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_put_segments(async_client, cleanup_projects, temp_projects_dir):
    """PUT /api/v1/projects/{uuid}/segments updates segments.json."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "PUT Segments"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Line one", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
            {"segment_index": 1, "script_line": "Line two", "start_time": 1.0, "end_time": 2.0, "duration": 1.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    updated = {
        "segments": [
            {"segment_index": 0, "script_line": "Edited line", "start_time": 0.0, "end_time": 1.5, "duration": 1.5},
        ]
    }
    resp = await async_client.put(f"/api/v1/projects/{project_uuid}/segments", json=updated)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["segments"]) == 1
    assert data["segments"][0]["script_line"] == "Edited line"
    assert data["segments"][0]["segment_index"] == 0


@pytest.mark.asyncio
async def test_split_segment_by_timestamp(async_client, cleanup_projects, temp_projects_dir):
    """POST split by timestamp divides segment correctly."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Split Test"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello world this is a test", "start_time": 0.0, "end_time": 4.0, "duration": 4.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/segments/0/split",
        json={"timestamp": 2.0}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["segments"]) == 2
    assert data["segments"][0]["start_time"] == 0.0
    assert data["segments"][0]["end_time"] == 2.0
    assert data["segments"][0]["duration"] == 2.0
    assert data["segments"][1]["start_time"] == 2.0
    assert data["segments"][1]["end_time"] == 4.0
    assert data["segments"][1]["duration"] == 2.0
    assert data["segments"][0]["segment_index"] == 0
    assert data["segments"][1]["segment_index"] == 1


@pytest.mark.asyncio
async def test_split_segment_by_word_index(async_client, cleanup_projects, temp_projects_dir):
    """POST split by word_index divides segment correctly."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Split Word"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello world this is a test", "start_time": 0.0, "end_time": 5.0, "duration": 5.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    words = {
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
            {"word": "this", "start": 1.1, "end": 1.5},
            {"word": "is", "start": 1.6, "end": 2.0},
            {"word": "a", "start": 2.1, "end": 2.5},
            {"word": "test", "start": 2.6, "end": 3.0},
        ]
    }
    with open(os.path.join(conduit_dir, "words.json"), "w", encoding="utf-8") as f:
        json.dump(words, f)

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/segments/0/split",
        json={"word_index": 3}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["segments"]) == 2
    assert data["segments"][0]["end_time"] == 1.6
    assert data["segments"][1]["start_time"] == 1.6


@pytest.mark.asyncio
async def test_split_segment_invalid_bounds(async_client, cleanup_projects, temp_projects_dir):
    """POST split returns 400 for out-of-bounds timestamp."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Split Invalid"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/segments/0/split",
        json={"timestamp": 0.0}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_merge_segments(async_client, cleanup_projects, temp_projects_dir):
    """POST merge combines segment with next and updates timing."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Merge Test"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
            {"segment_index": 1, "script_line": "world", "start_time": 1.0, "end_time": 2.0, "duration": 1.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/0/merge")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["segments"]) == 1
    assert data["segments"][0]["script_line"] == "Hello world"
    assert data["segments"][0]["start_time"] == 0.0
    assert data["segments"][0]["end_time"] == 2.0
    assert data["segments"][0]["duration"] == 2.0
    assert data["segments"][0]["segment_index"] == 0


@pytest.mark.asyncio
async def test_merge_last_segment(async_client, cleanup_projects, temp_projects_dir):
    """POST merge on last segment returns 400."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Merge Last"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/0/merge")
    assert resp.status_code == 400
    assert "cannot merge last segment" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_prompts_success(async_client, cleanup_projects, temp_projects_dir):
    """POST /api/v1/projects/{uuid}/segments/prompts returns 200 with prompts."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Prompt Test"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Advance state to step_2_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")

    # Create segments.json (Pass 1 complete)
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello world.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
            },
            {
                "segment_index": 1,
                "script_line": "This is a test.",
                "start_time": 1.1,
                "end_time": 2.5,
                "duration": 1.4,
            },
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    # Create characters.json
    characters = {
        "characters": [
            {"name": "Alice", "type": "speaking", "importance": "major", "description": "A curious girl"}
        ]
    }
    with open(os.path.join(temp_projects_dir, project_uuid, "characters.json"), "w", encoding="utf-8") as f:
        json.dump(characters, f)

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
                                "content": json.dumps({
                                    "segments": [
                                        {
                                            "segment_index": 0,
                                            "script_line": "Hello world.",
                                            "segment_prompt": "A young girl named Alice waves hello in a sunny meadow.",
                                            "characters_present": ["Alice"],
                                            "start_time": 0.0,
                                            "end_time": 1.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 1,
                                            "script_line": "This is a test.",
                                            "segment_prompt": "Alice stands at a chalkboard writing a test.",
                                            "characters_present": ["Alice"],
                                            "start_time": 1.1,
                                            "end_time": 2.5,
                                            "duration": 1.4,
                                        },
                                    ]
                                }),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "segments" in data
        assert len(data["segments"]) == 2
        assert data["segments"][0]["segment_prompt"] == "A young girl named Alice waves hello in a sunny meadow."
        assert data["segments"][0]["characters_present"] == ["Alice"]

        # Assert prompt contains both segments and characters
        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["messages"][0]["role"] == "system"
        assert "scene director" in body["messages"][0]["content"]
        assert "Cinematic wide shot, photorealistic 3D render" in body["messages"][0]["content"]
        assert "no text, no watermark" in body["messages"][0]["content"]
        assert "over-the-shoulder" in body["messages"][0]["content"]
        prompt = body["messages"][1]["content"]
        assert "Hello world." in prompt
        assert "Alice" in prompt

    # Assert segments.json updated with prompts
    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["segments"][0]["segment_prompt"] == "A young girl named Alice waves hello in a sunny meadow."
    assert saved["segments"][0]["characters_present"] == ["Alice"]

    # Assert main state updated to step_3_complete
    state_resp = await async_client.get(f"/api/v1/projects/{project_uuid}")
    assert state_resp.status_code == 200
    project_state = state_resp.json()["state"]
    assert project_state == "step_3_complete"

    # Assert state.json updated
    state_path = os.path.join(conduit_dir, "state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_3_pass_2_complete") is True


@pytest.mark.asyncio
async def test_generate_prompts_prerequisite_not_met(async_client, cleanup_projects):
    """POST prompts returns 409 when segments.json is missing."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Prereq Prompt"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
    assert resp.status_code == 409
    assert "Segment breakdown required first" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_prompts_fireworks_failure(async_client, cleanup_projects, temp_projects_dir):
    """POST prompts returns 502 when Fireworks API fails."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Prompt Fail"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0}
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
        assert resp.status_code == 502


@pytest.mark.asyncio
async def test_generate_prompts_authentication_error(async_client, cleanup_projects, temp_projects_dir):
    """POST prompts returns 502 on AI authentication error."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Prompt Auth Fail"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0}
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
        assert resp.status_code == 502
        assert "AI service authentication failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_prompts_rate_limit_error(async_client, cleanup_projects, temp_projects_dir):
    """POST prompts returns 429 on AI rate limit error."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Prompt Rate Limit"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0}
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
        assert resp.status_code == 429
        assert "AI service rate limited, retry shortly" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_prompts_batch_fallback(async_client, cleanup_projects, temp_projects_dir):
    """POST prompts uses overlapping batch fallback when token limit is exceeded."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Batch Fallback"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")

    # Create 26 segments to trigger batch fallback
    segments = {"segments": []}
    for i in range(26):
        segments["segments"].append({
            "segment_index": i,
            "script_line": f"Line {i}.",
            "start_time": float(i),
            "end_time": float(i + 1),
            "duration": 1.0,
        })
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    characters = {"characters": [{"name": "Alice", "type": "speaking", "importance": "major", "description": "A girl"}]}
    with open(os.path.join(temp_projects_dir, project_uuid, "characters.json"), "w", encoding="utf-8") as f:
        json.dump(characters, f)

    call_count = 0
    def side_effect(request):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call (single call) should fail with 413
            return httpx.Response(413, json={"error": "Context length exceeded"})

        # Batch calls
        if call_count == 2:
            # Batch 0 response: segments 0-24
            batch_segments = []
            for i in range(25):
                batch_segments.append({
                    "segment_index": i,
                    "script_line": f"Line {i}.",
                    "segment_prompt": f"Batch0 prompt for line {i}.",
                    "characters_present": ["Alice"],
                    "start_time": float(i),
                    "end_time": float(i + 1),
                    "duration": 1.0,
                })
            return httpx.Response(200, json={
                "id": "test-id",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"segments": batch_segments}),
                        },
                        "finish_reason": "stop",
                    }
                ],
            })
        else:
            # Batch 1 response: segments 20-25
            batch_segments = []
            for i in range(20, 26):
                batch_segments.append({
                    "segment_index": i,
                    "script_line": f"Line {i}.",
                    "segment_prompt": f"Batch1 prompt for line {i}.",
                    "characters_present": ["Alice"],
                    "start_time": float(i),
                    "end_time": float(i + 1),
                    "duration": 1.0,
                })
            return httpx.Response(200, json={
                "id": "test-id",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/routers/kimi-k2p6-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"segments": batch_segments}),
                        },
                        "finish_reason": "stop",
                    }
                ],
            })

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(side_effect=side_effect)

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert len(data["segments"]) == 26
        # Overlapping segments should use later batch result (batch 1 overwrites batch 0 for 20-24)
        assert data["segments"][20]["segment_prompt"] == "Batch1 prompt for line 20."
        assert data["segments"][24]["segment_prompt"] == "Batch1 prompt for line 24."
        assert data["segments"][25]["segment_prompt"] == "Batch1 prompt for line 25."

    # Verify segments.json preserved and updated
    with open(os.path.join(conduit_dir, "segments.json"), "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved["segments"]) == 26
    assert saved["segments"][20]["segment_prompt"] == "Batch1 prompt for line 20."
    assert saved["segments"][25]["segment_prompt"] == "Batch1 prompt for line 25."
