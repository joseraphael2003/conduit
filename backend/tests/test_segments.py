import os
import json
import pytest
import httpx
import respx
from unittest.mock import patch
from openai._exceptions import APIError

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


@pytest.mark.asyncio
async def test_flashback_non_monotonic(async_client, cleanup_projects, temp_projects_dir):
    """Pass 2 resolves flashback (non-monotonic) to earlier version."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Flashback Test"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    project_dir = os.path.join(temp_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")

    # Write script
    script_path = os.path.join(conduit_dir, "source_of_truth_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("Alice as a child. Alice as an adult. Alice as a child again.")

    # Write characters.json with 2 versions
    characters = {
        "characters": [
            {
                "name": "Alice (Young)",
                "type": "speaking",
                "importance": "major",
                "description": "A young girl.",
                "base_name": "Alice",
                "version_label": "Young",
                "version_index": 0,
                "identity_anchor": "Blue-eyed with brown hair",
            },
            {
                "name": "Alice (Adult)",
                "type": "speaking",
                "importance": "major",
                "description": "A grown woman.",
                "base_name": "Alice",
                "version_label": "Adult",
                "version_index": 1,
                "identity_anchor": "Blue-eyed with brown hair",
            },
        ]
    }
    characters_path = os.path.join(project_dir, "characters.json")
    with open(characters_path, "w", encoding="utf-8") as f:
        json.dump(characters, f)

    # Write 5 segments (simulating Pass 1 complete)
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Alice as a child.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
            {"segment_index": 1, "script_line": "Some transition.", "start_time": 1.0, "end_time": 2.0, "duration": 1.0},
            {"segment_index": 2, "script_line": "Alice as an adult.", "start_time": 2.0, "end_time": 3.0, "duration": 1.0},
            {"segment_index": 3, "script_line": "Another transition.", "start_time": 3.0, "end_time": 4.0, "duration": 1.0},
            {"segment_index": 4, "script_line": "Alice as a child again.", "start_time": 4.0, "end_time": 5.0, "duration": 1.0},
        ]
    }
    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments, f)

    # Mock Pass 2 to return versioned names
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
                                "content": json.dumps({
                                    "segments": [
                                        {
                                            "segment_index": 0,
                                            "script_line": "Alice as a child.",
                                            "segment_prompt": "Young Alice in a garden.",
                                            "characters_present": ["Alice (Young)"],
                                            "start_time": 0.0,
                                            "end_time": 1.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 1,
                                            "script_line": "Some transition.",
                                            "segment_prompt": "A transition scene.",
                                            "characters_present": [],
                                            "start_time": 1.0,
                                            "end_time": 2.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 2,
                                            "script_line": "Alice as an adult.",
                                            "segment_prompt": "Adult Alice at a desk.",
                                            "characters_present": ["Alice (Adult)"],
                                            "start_time": 2.0,
                                            "end_time": 3.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 3,
                                            "script_line": "Another transition.",
                                            "segment_prompt": "Another transition scene.",
                                            "characters_present": [],
                                            "start_time": 3.0,
                                            "end_time": 4.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 4,
                                            "script_line": "Alice as a child again.",
                                            "segment_prompt": "Young Alice in a garden again.",
                                            "characters_present": ["Alice (Young)"],
                                            "start_time": 4.0,
                                            "end_time": 5.0,
                                            "duration": 1.0,
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
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["segments"]) == 5

        # Build name -> version_index map from characters.json
        with open(characters_path, "r", encoding="utf-8") as f:
            chars = json.load(f)
        name_to_index = {c["name"]: c["version_index"] for c in chars["characters"]}

        seg0 = data["segments"][0]
        seg2 = data["segments"][2]
        seg4 = data["segments"][4]

        assert seg0["characters_present"] == ["Alice (Young)"]
        assert seg2["characters_present"] == ["Alice (Adult)"]
        assert seg4["characters_present"] == ["Alice (Young)"]

        # Assert version_index resolution
        assert name_to_index[seg0["characters_present"][0]] == 0
        assert name_to_index[seg2["characters_present"][0]] == 1
        assert name_to_index[seg4["characters_present"][0]] == 0

    # Verify persistence
    with open(segments_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["segments"][4]["characters_present"] == ["Alice (Young)"]
    assert saved["segments"][2]["characters_present"] == ["Alice (Adult)"]


@pytest.mark.asyncio
async def test_end_to_end_override(async_client, cleanup_projects, temp_projects_dir):
    """Full flow: extract, timeline, prompts, then override segment 2 with pinned version."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Override E2E"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")

    project_dir = os.path.join(temp_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    script_path = os.path.join(conduit_dir, "source_of_truth_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("Alice as a child. Alice as an adult. Alice as a child again.")

    # Mock extract characters (Call 1)
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
                                "content": json.dumps({
                                    "characters": [
                                        {
                                            "name": "Alice",
                                            "type": "speaking",
                                            "importance": "major",
                                            "description": "A girl who ages.",
                                            "base_name": "Alice",
                                            "version_label": "default",
                                            "version_index": 0,
                                            "identity_anchor": "Blue-eyed with brown hair",
                                        }
                                    ]
                                }),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
        extract_resp = await async_client.post(f"/api/v1/projects/{project_uuid}/characters/extract")
        assert extract_resp.status_code == 200

    # Mock timeline (detect versions)
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
                                "content": json.dumps({
                                    "characters": [
                                        {
                                            "name": "Alice (Young)",
                                            "type": "speaking",
                                            "importance": "major",
                                            "description": "A young girl.",
                                            "base_name": "Alice",
                                            "version_label": "Young",
                                            "version_index": 0,
                                            "identity_anchor": "Blue-eyed with brown hair",
                                            "appears_from": "00:00",
                                        },
                                        {
                                            "name": "Alice (Adult)",
                                            "type": "speaking",
                                            "importance": "major",
                                            "description": "A grown woman.",
                                            "base_name": "Alice",
                                            "version_label": "Adult",
                                            "version_index": 1,
                                            "identity_anchor": "Blue-eyed with brown hair",
                                            "appears_from": "05:00",
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
        timeline_resp = await async_client.post(f"/api/v1/projects/{project_uuid}/characters/timeline")
        assert timeline_resp.status_code == 200

    # Advance to step 2
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    # Write segments
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Alice as a child.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
            {"segment_index": 1, "script_line": "Some transition.", "start_time": 1.0, "end_time": 2.0, "duration": 1.0},
            {"segment_index": 2, "script_line": "Alice as an adult.", "start_time": 2.0, "end_time": 3.0, "duration": 1.0},
            {"segment_index": 3, "script_line": "Another transition.", "start_time": 3.0, "end_time": 4.0, "duration": 1.0},
            {"segment_index": 4, "script_line": "Alice as a child again.", "start_time": 4.0, "end_time": 5.0, "duration": 1.0},
        ]
    }
    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments, f)

    # Mock Pass 2 prompts
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
                                "content": json.dumps({
                                    "segments": [
                                        {
                                            "segment_index": 0,
                                            "script_line": "Alice as a child.",
                                            "segment_prompt": "Young Alice in a garden.",
                                            "characters_present": ["Alice (Young)"],
                                            "start_time": 0.0,
                                            "end_time": 1.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 1,
                                            "script_line": "Some transition.",
                                            "segment_prompt": "A transition scene.",
                                            "characters_present": [],
                                            "start_time": 1.0,
                                            "end_time": 2.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 2,
                                            "script_line": "Alice as an adult.",
                                            "segment_prompt": "Adult Alice at a desk.",
                                            "characters_present": ["Alice (Adult)"],
                                            "start_time": 2.0,
                                            "end_time": 3.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 3,
                                            "script_line": "Another transition.",
                                            "segment_prompt": "Another transition scene.",
                                            "characters_present": [],
                                            "start_time": 3.0,
                                            "end_time": 4.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 4,
                                            "script_line": "Alice as a child again.",
                                            "segment_prompt": "Young Alice in a garden again.",
                                            "characters_present": ["Alice (Young)"],
                                            "start_time": 4.0,
                                            "end_time": 5.0,
                                            "duration": 1.0,
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
        assert resp.status_code == 200
        data = resp.json()
        assert data["segments"][2]["characters_present"] == ["Alice (Adult)"]
        assert "Adult" in data["segments"][2]["segment_prompt"]

    # Override segment 2 via regen endpoint with pinned young version
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
                                            "segment_index": 2,
                                            "script_line": "Alice as an adult.",
                                            "segment_prompt": "Young Alice at a desk in a flashback.",
                                            "characters_present": ["Alice (Young)"],
                                            "start_time": 2.0,
                                            "end_time": 3.0,
                                            "duration": 1.0,
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
        override_resp = await async_client.post(
            f"/api/v1/projects/{project_uuid}/segments/2/prompt",
            json={"character_versions": {"Alice": "Alice (Young)"}},
        )
        assert override_resp.status_code == 200
        override_data = override_resp.json()
        assert override_data["characters_present"] == ["Alice (Young)"]
        assert "Young" in override_data["segment_prompt"]

        # Assert the prompt sent to Fireworks only included the pinned version
        request = route.calls.last.request
        body = json.loads(request.content)
        user_prompt = body["messages"][1]["content"]
        assert "Alice (Young)" in user_prompt
        # Extract the <characters> block to confirm filtering
        chars_start = user_prompt.find("<characters>")
        chars_end = user_prompt.find("</characters>")
        chars_block = user_prompt[chars_start:chars_end]
        assert "Alice (Young)" in chars_block
        assert "Alice (Adult)" not in chars_block

    # Verify persistence: reload segments.json
    with open(segments_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["segments"][2]["characters_present"] == ["Alice (Young)"]
    assert "Young" in saved["segments"][2]["segment_prompt"]


@pytest.mark.asyncio
async def test_pass2_versioned_characters(async_client, cleanup_projects, temp_projects_dir):
    """Mock Pass 2 with versioned characters. Assert versioned names in characters_present."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Versioned Pass2"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "The young hero trains.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
            },
            {
                "segment_index": 1,
                "script_line": "The old hero rests.",
                "start_time": 1.1,
                "end_time": 2.5,
                "duration": 1.4,
            },
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    characters = {
        "characters": [
            {"name": "Hero (young)", "base_name": "Hero", "type": "speaking", "importance": "major", "description": "A young hero"},
            {"name": "Hero (adult)", "base_name": "Hero", "type": "speaking", "importance": "major", "description": "An adult hero"},
        ]
    }
    with open(os.path.join(temp_projects_dir, project_uuid, "characters.json"), "w", encoding="utf-8") as f:
        json.dump(characters, f)

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
                                "content": json.dumps({
                                    "segments": [
                                        {
                                            "segment_index": 0,
                                            "script_line": "The young hero trains.",
                                            "segment_prompt": "A young hero training in a dojo.",
                                            "characters_present": ["Hero (young)"],
                                            "start_time": 0.0,
                                            "end_time": 1.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 1,
                                            "script_line": "The old hero rests.",
                                            "segment_prompt": "An old hero resting by the fire.",
                                            "characters_present": ["Hero (adult)"],
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
        assert len(data["segments"]) == 2
        assert data["segments"][0]["characters_present"] == ["Hero (young)"]
        assert data["segments"][1]["characters_present"] == ["Hero (adult)"]

    # Verify segments.json saved versioned names
    with open(os.path.join(conduit_dir, "segments.json"), "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["segments"][0]["characters_present"] == ["Hero (young)"]
    assert saved["segments"][1]["characters_present"] == ["Hero (adult)"]


@pytest.mark.asyncio
async def test_regenerate_single_segment(async_client, cleanup_projects, temp_projects_dir):
    """Mock regen endpoint for segment 2. Assert only segment 2 changes, others preserved."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Regen Single"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Line one",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "Prompt one",
                "characters_present": ["Alice"],
                "effect": "pan_left",
                "image_path": "/tmp/projects/test/images/0000.png",
            },
            {
                "segment_index": 1,
                "script_line": "Line two",
                "start_time": 1.0,
                "end_time": 2.0,
                "duration": 1.0,
                "segment_prompt": "Prompt two",
                "characters_present": ["Alice"],
                "effect": "zoom_in",
                "image_path": "/tmp/projects/test/images/0001.png",
            },
            {
                "segment_index": 2,
                "script_line": "Line three",
                "start_time": 2.0,
                "end_time": 3.0,
                "duration": 1.0,
                "segment_prompt": "Original prompt three",
                "characters_present": ["Bob"],
                "effect": "pan_right",
                "image_path": "/tmp/projects/test/images/0002.png",
            },
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

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
                                "content": json.dumps({
                                    "segments": [
                                        {
                                            "segment_index": 2,
                                            "script_line": "Line three",
                                            "segment_prompt": "Regenerated prompt three",
                                            "characters_present": ["Bob"],
                                            "start_time": 2.0,
                                            "end_time": 3.0,
                                            "duration": 1.0,
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

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/2/prompt")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["segment_prompt"] == "Regenerated prompt three"
        assert data["characters_present"] == ["Bob"]
        assert data["effect"] == "pan_right"
        assert data["image_path"] == "/tmp/projects/test/images/0002.png"

    # Verify segments.json: only segment 2 changed, others preserved
    with open(os.path.join(conduit_dir, "segments.json"), "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["segments"][0]["segment_prompt"] == "Prompt one"
    assert saved["segments"][1]["segment_prompt"] == "Prompt two"
    assert saved["segments"][2]["segment_prompt"] == "Regenerated prompt three"
    assert saved["segments"][2]["effect"] == "pan_right"
    assert saved["segments"][2]["image_path"] == "/tmp/projects/test/images/0002.png"


@pytest.mark.asyncio
async def test_regenerate_with_character_versions(async_client, cleanup_projects, temp_projects_dir):
    """Mock regen with character_versions mapping. Assert filtered version in characters_present."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Regen Versions"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "The hero returns.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "Original prompt",
                "characters_present": ["Hero (young)"],
                "effect": "none",
            },
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    characters = {
        "characters": [
            {"name": "Hero (young)", "base_name": "Hero", "type": "speaking", "importance": "major", "description": "A young hero"},
            {"name": "Hero (adult)", "base_name": "Hero", "type": "speaking", "importance": "major", "description": "An adult hero"},
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
                                            "script_line": "The hero returns.",
                                            "segment_prompt": "Adult hero prompt.",
                                            "characters_present": ["Hero (adult)"],
                                            "start_time": 0.0,
                                            "end_time": 1.0,
                                            "duration": 1.0,
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

        resp = await async_client.post(
            f"/api/v1/projects/{project_uuid}/segments/0/prompt",
            json={"character_versions": {"Hero": "Hero (adult)"}},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["characters_present"] == ["Hero (adult)"]
        assert data["segment_prompt"] == "Adult hero prompt."

        # Verify the prompt sent to Fireworks only included the selected version
        request = route.calls.last.request
        body = json.loads(request.content)
        prompt = body["messages"][1]["content"]
        assert "Hero (adult)" in prompt
        # Extract the <characters> block to confirm filtering
        chars_start = prompt.find("<characters>")
        chars_end = prompt.find("</characters>")
        chars_block = prompt[chars_start:chars_end]
        assert "Hero (adult)" in chars_block
        assert "Hero (young)" not in chars_block


@pytest.mark.asyncio
async def test_regenerate_bad_index(async_client, cleanup_projects, temp_projects_dir):
    """POST to out-of-range segment_index returns 400."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Bad Index"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Only line",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "Prompt",
                "characters_present": [],
            },
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/5/prompt")
    assert resp.status_code == 400
    assert "Invalid segment_index" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_breakdown_max_tokens(async_client, cleanup_projects, temp_projects_dir):
    """POST breakdown sends max_tokens=16000 to Fireworks."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Max Tokens"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    with open(os.path.join(conduit_dir, "source_of_truth_script.txt"), "w", encoding="utf-8") as f:
        f.write("Hello world.")
    with open(os.path.join(conduit_dir, "words.json"), "w", encoding="utf-8") as f:
        json.dump({"words": [{"word": "Hello", "start": 0.0, "end": 0.5}, {"word": "world", "start": 0.6, "end": 1.0}]}, f)

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
                                        }
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
        assert resp.status_code == 200

        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["max_tokens"] == 16000


@pytest.mark.asyncio
async def test_breakdown_invalid_json_502(async_client, cleanup_projects, temp_projects_dir):
    """POST breakdown returns 502 when Fireworks returns invalid JSON."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Invalid JSON"})
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
                                "content": "not json {",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/breakdown")
        assert resp.status_code == 502
        assert "AI request failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_returns_prompt_fields(async_client, cleanup_projects, temp_projects_dir):
    """GET /segments returns segment_prompt, characters_present, and image_path."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "GET Prompts"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello world.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "A sunny meadow.",
                "characters_present": ["Alice"],
                "image_path": "projects/test/images/0000.png",
            }
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/segments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["segments"][0]["segment_prompt"] == "A sunny meadow."
    assert data["segments"][0]["characters_present"] == ["Alice"]
    assert data["segments"][0]["image_path"] == "projects/test/images/0000.png"


@pytest.mark.asyncio
async def test_put_persists_incoming_prompt_edit(async_client, cleanup_projects, temp_projects_dir):
    """PUT /segments persists edited segment_prompt and characters_present."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "PUT Prompt Edit"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Original line.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "Original prompt",
                "characters_present": ["Alice"],
            }
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    updated = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Edited line.",
                "segment_prompt": "Edited prompt",
                "characters_present": ["Bob"],
            }
        ]
    }
    put_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/segments", json=updated)
    assert put_resp.status_code == 200

    get_resp = await async_client.get(f"/api/v1/projects/{project_uuid}/segments")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["segments"][0]["script_line"] == "Edited line."
    assert data["segments"][0]["segment_prompt"] == "Edited prompt"
    assert data["segments"][0]["characters_present"] == ["Bob"]


@pytest.mark.asyncio
async def test_put_preserves_omitted_fields(async_client, cleanup_projects, temp_projects_dir):
    """PUT /segments preserves omitted prompt fields from disk."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "PUT Preserve"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Original line.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "Original prompt",
                "characters_present": ["Alice"],
                "image_path": "projects/test/images/0000.png",
            }
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    updated = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Edited line.",
            }
        ]
    }
    put_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/segments", json=updated)
    assert put_resp.status_code == 200

    get_resp = await async_client.get(f"/api/v1/projects/{project_uuid}/segments")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["segments"][0]["script_line"] == "Edited line."
    assert data["segments"][0]["segment_prompt"] == "Original prompt"
    assert data["segments"][0]["characters_present"] == ["Alice"]
    assert data["segments"][0]["image_path"] == "projects/test/images/0000.png"


@pytest.mark.asyncio
async def test_pre_prompt_safety(async_client, cleanup_projects, temp_projects_dir):
    """GET and PUT on pre-prompt segments do not 422."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Pre-Prompt"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello world.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
            }
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    get_resp = await async_client.get(f"/api/v1/projects/{project_uuid}/segments")
    assert get_resp.status_code == 200

    put_payload = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello world.",
            }
        ]
    }
    put_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/segments", json=put_payload)
    assert put_resp.status_code == 200


@pytest.mark.asyncio
async def test_pass2_valueerror_502(async_client, cleanup_projects, temp_projects_dir):
    """POST /segments/prompts returns 502 when _generate_prompts_for_batch raises ValueError."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Pass2 ValueError"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
            }
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    characters = {"characters": [{"name": "Alice", "type": "speaking", "importance": "major", "description": "A girl"}]}
    with open(os.path.join(temp_projects_dir, project_uuid, "characters.json"), "w", encoding="utf-8") as f:
        json.dump(characters, f)

    with patch("routers.segments._generate_prompts_for_batch", side_effect=ValueError("bad response")):
        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
        assert resp.status_code == 502
        assert "AI returned an unexpected response" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_regenerate_valueerror_502(async_client, cleanup_projects, temp_projects_dir):
    """POST /segments/{index}/prompt returns 502 when _generate_prompts_for_batch raises ValueError."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Regen ValueError"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "Original prompt",
                "characters_present": ["Alice"],
            }
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    characters = {"characters": [{"name": "Alice", "type": "speaking", "importance": "major", "description": "A girl"}]}
    with open(os.path.join(temp_projects_dir, project_uuid, "characters.json"), "w", encoding="utf-8") as f:
        json.dump(characters, f)

    with patch("routers.segments._generate_prompts_for_batch", side_effect=ValueError("bad response")):
        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/0/prompt")
        assert resp.status_code == 502
        assert "AI returned an unexpected response" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_split_preserves_other_segment_fields(async_client, cleanup_projects, temp_projects_dir):
    """Split resets prompt fields on new halves but preserves them on untouched segments."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Split Preserve"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "First line",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "prompt for segment 0",
                "characters_present": ["Alice (young)"],
                "image_path": "images/0000.png",
                "effect": "pan_left",
            },
            {
                "segment_index": 1,
                "script_line": "Second line",
                "start_time": 1.0,
                "end_time": 4.0,
                "duration": 3.0,
                "segment_prompt": "old prompt",
                "characters_present": ["Bob"],
                "image_path": "images/0001.png",
                "effect": "zoom_in",
            },
            {
                "segment_index": 2,
                "script_line": "Third line",
                "start_time": 4.0,
                "end_time": 5.0,
                "duration": 1.0,
            },
            {
                "segment_index": 3,
                "script_line": "Fourth line",
                "start_time": 5.0,
                "end_time": 6.0,
                "duration": 1.0,
                "segment_prompt": "prompt for segment 3",
                "characters_present": ["Alice (young)"],
                "image_path": "images/0003.png",
                "effect": "pan_right",
            },
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/segments/1/split",
        json={"timestamp": 2.0}
    )
    assert resp.status_code == 200
    data = resp.json()
    segs = data["segments"]

    # Count increased by 1
    assert len(segs) == 5

    # segment_index contiguous 0..4
    assert [s["segment_index"] for s in segs] == [0, 1, 2, 3, 4]

    # Segment 0 untouched
    assert segs[0]["segment_prompt"] == "prompt for segment 0"
    assert segs[0]["characters_present"] == ["Alice (young)"]
    assert segs[0]["image_path"] == "images/0000.png"
    assert segs[0]["effect"] == "pan_left"

    # Segment 4 (was originally segment 3) untouched
    assert segs[4]["segment_prompt"] == "prompt for segment 3"
    assert segs[4]["characters_present"] == ["Alice (young)"]
    assert segs[4]["image_path"] == "images/0003.png"
    assert segs[4]["effect"] == "pan_right"

    # New left half (index 1)
    assert segs[1]["segment_prompt"] == ""
    assert segs[1]["characters_present"] == []
    assert "image_path" not in segs[1]
    assert segs[1]["effect"] == "zoom_in"
    assert segs[1]["start_time"] == 1.0
    assert segs[1]["end_time"] == 2.0
    assert segs[1]["duration"] == 1.0

    # New right half (index 2)
    assert segs[2]["segment_prompt"] == ""
    assert segs[2]["characters_present"] == []
    assert "image_path" not in segs[2]
    assert segs[2]["effect"] == "zoom_in"
    assert segs[2]["start_time"] == 2.0
    assert segs[2]["end_time"] == 4.0
    assert segs[2]["duration"] == 2.0


@pytest.mark.asyncio
async def test_merge_preserves_other_segment_fields(async_client, cleanup_projects, temp_projects_dir):
    """Merge resets prompt fields on merged result but preserves them on untouched segments."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Merge Preserve"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "First line",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "segment_prompt": "prompt for segment 0",
                "characters_present": ["Alice (young)"],
                "image_path": "images/0000.png",
                "effect": "pan_left",
            },
            {
                "segment_index": 1,
                "script_line": "Second line",
                "start_time": 1.0,
                "end_time": 2.0,
                "duration": 1.0,
                "segment_prompt": "old prompt",
                "characters_present": ["Bob"],
                "image_path": "images/0001.png",
                "effect": "zoom_in",
            },
            {
                "segment_index": 2,
                "script_line": "Third line",
                "start_time": 2.0,
                "end_time": 3.0,
                "duration": 1.0,
                "segment_prompt": "prompt for segment 2",
                "characters_present": ["Charlie"],
                "image_path": "images/0002.png",
                "effect": "pan_up",
            },
            {
                "segment_index": 3,
                "script_line": "Fourth line",
                "start_time": 3.0,
                "end_time": 4.0,
                "duration": 1.0,
                "segment_prompt": "prompt for segment 3",
                "characters_present": ["Alice (young)"],
                "image_path": "images/0003.png",
                "effect": "pan_right",
            },
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/1/merge")
    assert resp.status_code == 200
    data = resp.json()
    segs = data["segments"]

    # Count decreased by 1
    assert len(segs) == 3

    # segment_index contiguous 0..2
    assert [s["segment_index"] for s in segs] == [0, 1, 2]

    # Segment 0 untouched
    assert segs[0]["segment_prompt"] == "prompt for segment 0"
    assert segs[0]["characters_present"] == ["Alice (young)"]
    assert segs[0]["image_path"] == "images/0000.png"
    assert segs[0]["effect"] == "pan_left"

    # Segment 2 (was originally segment 3) untouched
    assert segs[2]["segment_prompt"] == "prompt for segment 3"
    assert segs[2]["characters_present"] == ["Alice (young)"]
    assert segs[2]["image_path"] == "images/0003.png"
    assert segs[2]["effect"] == "pan_right"

    # Merged result (index 1)
    assert segs[1]["segment_prompt"] == ""
    assert segs[1]["characters_present"] == []
    assert "image_path" not in segs[1]
    assert segs[1]["effect"] == "zoom_in"
    assert segs[1]["script_line"] == "Second line Third line"
    assert segs[1]["start_time"] == 1.0
    assert segs[1]["end_time"] == 3.0
    assert segs[1]["duration"] == 2.0


@pytest.mark.asyncio
async def test_breakdown_assigns_segment_ids(async_client, cleanup_projects, temp_projects_dir):
    """Mock breakdown call returns segments with unique segment_ids."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Segment ID Test"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    with open(os.path.join(conduit_dir, "source_of_truth_script.txt"), "w", encoding="utf-8") as f:
        f.write("Hello world. This is a test.")
    with open(os.path.join(conduit_dir, "words.json"), "w", encoding="utf-8") as f:
        json.dump({"words": [{"word": "Hello", "start": 0.0, "end": 0.5}, {"word": "world", "start": 0.6, "end": 1.0}, {"word": "This", "start": 1.1, "end": 1.5}, {"word": "is", "start": 1.6, "end": 1.8}, {"word": "a", "start": 1.9, "end": 2.0}, {"word": "test", "start": 2.1, "end": 2.5}]}, f)

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
                                "content": json.dumps({
                                    "segments": [
                                        {"segment_index": 0, "script_line": "Hello world.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
                                        {"segment_index": 1, "script_line": "This is a test.", "start_time": 1.1, "end_time": 2.5, "duration": 1.4},
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
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["segments"]) == 2
        ids = [s["segment_id"] for s in data["segments"]]
        assert all(ids)
        assert len(set(ids)) == 2
        assert ids[0] != ids[1]


@pytest.mark.asyncio
async def test_split_assigns_fresh_ids(async_client, cleanup_projects, temp_projects_dir):
    """Split creates new segments with fresh segment_ids and preserves untouched segment_id."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Split IDs"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    original_id_0 = "seg-id-0-aaaaaaaa"
    original_id_1 = "seg-id-1-bbbbbbbb"
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello world", "start_time": 0.0, "end_time": 4.0, "duration": 4.0, "segment_id": original_id_0},
            {"segment_index": 1, "script_line": "Goodbye", "start_time": 4.0, "end_time": 5.0, "duration": 1.0, "segment_id": original_id_1},
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
    assert len(data["segments"]) == 3
    ids = [s["segment_id"] for s in data["segments"]]
    assert ids[0] != original_id_0
    assert ids[1] != original_id_0
    assert ids[0] != ids[1]
    assert ids[2] == original_id_1


@pytest.mark.asyncio
async def test_merge_assigns_fresh_id(async_client, cleanup_projects, temp_projects_dir):
    """Merge creates a new segment with a fresh segment_id."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Merge IDs"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    original_id_0 = "seg-id-0-aaaaaaaa"
    original_id_1 = "seg-id-1-bbbbbbbb"
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello", "start_time": 0.0, "end_time": 1.0, "duration": 1.0, "segment_id": original_id_0},
            {"segment_index": 1, "script_line": "world", "start_time": 1.0, "end_time": 2.0, "duration": 1.0, "segment_id": original_id_1},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/0/merge")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["segments"]) == 1
    new_id = data["segments"][0]["segment_id"]
    assert new_id != original_id_0
    assert new_id != original_id_1
    assert new_id


@pytest.mark.asyncio
async def test_update_preserves_segment_ids(async_client, cleanup_projects, temp_projects_dir):
    """PUT update without segment_id preserves the original segment_id."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Update Preserve ID"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    original_id = "seg-id-preserve-1234"
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Line one", "start_time": 0.0, "end_time": 1.0, "duration": 1.0, "segment_id": original_id},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    updated = {
        "segments": [
            {"segment_index": 0, "script_line": "Edited line"},
        ]
    }
    resp = await async_client.put(f"/api/v1/projects/{project_uuid}/segments", json=updated)
    assert resp.status_code == 200
    data = resp.json()
    assert data["segments"][0]["segment_id"] == original_id
    assert data["segments"][0]["script_line"] == "Edited line"


@pytest.mark.asyncio
async def test_update_backfills_missing_segment_id(async_client, cleanup_projects, temp_projects_dir):
    """PUT update backfills missing segment_id with a new UUID."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Update Backfill ID"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Line one", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    updated = {
        "segments": [
            {"segment_index": 0, "script_line": "Edited line"},
        ]
    }
    resp = await async_client.put(f"/api/v1/projects/{project_uuid}/segments", json=updated)
    assert resp.status_code == 200
    data = resp.json()
    assert data["segments"][0]["segment_id"]
    assert isinstance(data["segments"][0]["segment_id"], str)
    assert len(data["segments"][0]["segment_id"]) > 0


@pytest.mark.asyncio
async def test_generate_prompts_max_tokens_16000(async_client, cleanup_projects, temp_projects_dir):
    """POST prompts sends max_tokens=16000 to Fireworks."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Prompt Max Tokens"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

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
                                        {"segment_index": 0, "script_line": "Hello.", "segment_prompt": "A prompt.", "characters_present": [], "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
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
        assert resp.status_code == 200

        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["max_tokens"] == 16000


@pytest.mark.asyncio
async def test_generate_prompts_truncation_triggers_fallback(async_client, cleanup_projects, temp_projects_dir):
    """POST prompts triggers batch fallback when primary call is truncated."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Truncation Fallback"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
            {"segment_index": 1, "script_line": "World.", "start_time": 1.0, "end_time": 2.0, "duration": 1.0},
        ]
    }
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
            return httpx.Response(502, json={"error": "truncated"})
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
                                "segments": [
                                    {"segment_index": 0, "script_line": "Hello.", "segment_prompt": "Prompt 0.", "characters_present": [], "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
                                    {"segment_index": 1, "script_line": "World.", "segment_prompt": "Prompt 1.", "characters_present": [], "start_time": 1.0, "end_time": 2.0, "duration": 1.0},
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
        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "segments" in data
        assert len(data["segments"]) == 2
        assert data["segments"][0]["segment_prompt"] == "Prompt 0."
        assert data["segments"][1]["segment_prompt"] == "Prompt 1."


@pytest.mark.asyncio
async def test_generate_prompts_missing_segment_index_resilience(async_client, cleanup_projects, temp_projects_dir):
    """POST prompts returns 200 when Fireworks omits segment_index for one item.

    Segments with a matching segment_index get their prompt fields populated.
    The segment whose index was omitted retains empty/default prompt fields.
    """
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Missing Segment Index"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
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
            {
                "segment_index": 2,
                "script_line": "Final line here.",
                "start_time": 2.6,
                "end_time": 3.5,
                "duration": 0.9,
            },
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    characters = {
        "characters": [
            {"name": "Alice", "type": "speaking", "importance": "major", "description": "A curious girl"}
        ]
    }
    with open(os.path.join(temp_projects_dir, project_uuid, "characters.json"), "w", encoding="utf-8") as f:
        json.dump(characters, f)

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
                                "content": json.dumps({
                                    "segments": [
                                        {
                                            "segment_index": 0,
                                            "script_line": "Hello world.",
                                            "segment_prompt": "Alice waves hello.",
                                            "characters_present": ["Alice"],
                                            "start_time": 0.0,
                                            "end_time": 1.0,
                                            "duration": 1.0,
                                        },
                                        {
                                            "segment_index": 2,
                                            "script_line": "Final line here.",
                                            "segment_prompt": "Alice sits down.",
                                            "characters_present": ["Alice"],
                                            "start_time": 2.6,
                                            "end_time": 3.5,
                                            "duration": 0.9,
                                        },
                                        # Intentionally missing segment_index for segment 1
                                        {
                                            "script_line": "This is a test.",
                                            "segment_prompt": "Alice writes a test.",
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
        assert len(data["segments"]) == 3

        # Segments 0 and 2 should have populated prompts
        assert data["segments"][0]["segment_prompt"] == "Alice waves hello."
        assert data["segments"][0]["characters_present"] == ["Alice"]
        assert data["segments"][2]["segment_prompt"] == "Alice sits down."
        assert data["segments"][2]["characters_present"] == ["Alice"]

        # Segment 1 (missing segment_index in response) should retain empty defaults
        assert data["segments"][1]["segment_prompt"] == ""
        assert data["segments"][1]["characters_present"] == []

    # Verify persistence in segments.json
    with open(os.path.join(conduit_dir, "segments.json"), "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["segments"][0]["segment_prompt"] == "Alice waves hello."
    assert saved["segments"][0]["characters_present"] == ["Alice"]
    assert saved["segments"][2]["segment_prompt"] == "Alice sits down."
    assert saved["segments"][2]["characters_present"] == ["Alice"]
    assert saved["segments"][1]["segment_prompt"] == ""
    assert saved["segments"][1]["characters_present"] == []

    # Assert state.json updated
    state_path = os.path.join(conduit_dir, "state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    assert state_data.get("step_3_pass_2_complete") is True


@pytest.mark.asyncio
async def test_generate_prompts_bad_json_no_fallback(async_client, cleanup_projects, temp_projects_dir):
    """POST prompts returns 502 on non-truncation APIError without fallback."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Bad JSON No Fallback"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with respx.mock:
        respx.post("https://api.fireworks.ai/inference/v1/chat/completions").mock(
            return_value=httpx.Response(500, json={"error": "some random error"})
        )

        resp = await async_client.post(f"/api/v1/projects/{project_uuid}/segments/prompts")
        assert resp.status_code == 502
