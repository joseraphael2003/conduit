import os
import json
import pytest
import pytest_asyncio
import httpx
import respx
from httpx import Request

# We import the app module for test-client setup
from main import app
import services.state as state_module


@pytest.mark.asyncio
async def test_create_project_valid(async_client, cleanup_projects):
    """POST /api/v1/projects with valid name returns 201 and project data."""
    response = await async_client.post("/api/v1/projects", json={"name": "My Project"})
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    data = response.json()
    assert "uuid" in data, "Response should contain project uuid"
    assert data["name"] == "My Project", "Project name should match"
    assert data["state"] == "created", "Project state should be 'created'"
    assert "created_at" in data, "Response should contain created_at"
    assert "updated_at" in data, "Response should contain updated_at"


@pytest.mark.asyncio
async def test_create_project_empty_name(async_client, cleanup_projects):
    """POST /api/v1/projects with empty name returns 422."""
    response = await async_client.post("/api/v1/projects", json={"name": ""})
    assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_list_projects(async_client, cleanup_projects):
    """GET /api/v1/projects returns 200 and a list."""
    # Ensure at least one project exists
    await async_client.post("/api/v1/projects", json={"name": "List Test"})
    response = await async_client.get("/api/v1/projects")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "projects" in data, "Response should contain 'projects' key"
    assert isinstance(data["projects"], list), "projects should be a list"


@pytest.mark.asyncio
async def test_get_project(async_client, cleanup_projects, created_project):
    """GET /api/v1/projects/{uuid} returns 200 with correct project."""
    project_uuid = created_project["uuid"]
    response = await async_client.get(f"/api/v1/projects/{project_uuid}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["uuid"] == project_uuid, "UUID should match"
    assert data["name"] == created_project["name"], "Name should match"


@pytest.mark.asyncio
async def test_delete_project(async_client, cleanup_projects, created_project):
    """DELETE /api/v1/projects/{uuid} returns 204."""
    project_uuid = created_project["uuid"]
    response = await async_client.delete(f"/api/v1/projects/{project_uuid}")
    assert response.status_code == 204, f"Expected 204, got {response.status_code}: {response.text}"
    # Verify deletion
    get_response = await async_client.get(f"/api/v1/projects/{project_uuid}")
    assert get_response.status_code == 404, "Project should be deleted"


@pytest.mark.asyncio
async def test_cascade_state_machine(async_client, cleanup_projects):
    """Test the cascade state machine through step updates."""
    # Create project → state is created
    create_resp = await async_client.post("/api/v1/projects", json={"name": "State Machine Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    assert project["state"] == "created", "Initial state should be 'created'"
    project_uuid = project["uuid"]

    # PUT step/1 → state is step_1_complete
    step1_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_resp.status_code == 200, f"Step 1 failed: {step1_resp.text}"
    step1_data = step1_resp.json()
    assert step1_data["state"] == "step_1_complete", "State should be 'step_1_complete' after step 1"

    # PUT step/2 → state is step_2_complete
    step2_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")
    assert step2_resp.status_code == 200, f"Step 2 failed: {step2_resp.text}"
    step2_data = step2_resp.json()
    assert step2_data["state"] == "step_2_complete", "State should be 'step_2_complete' after step 2"

    # PUT step/1 again (invalidate) → endpoint invalidates then re-completes step 1
    step1_again_resp = await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    assert step1_again_resp.status_code == 200, f"Re-PUT step 1 failed: {step1_again_resp.text}"
    step1_again_data = step1_again_resp.json()
    assert step1_again_data["state"] == "step_1_complete", "State should be 'step_1_complete' after re-PUT step 1"


@pytest.mark.asyncio
async def test_invalidate_downstream_step_2(async_client, cleanup_projects, temp_projects_dir):
    """Invalidate from Step 2 resets state to step_1_complete, deletes segments.json, clears downstream sub-steps."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Cascade Step 2"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Advance to step_3_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/3")

    # Set up sub-step state
    state_module.set_sub_step_state(project_uuid, "step_2_call_1_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_2_call_2_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_3_pass_1_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_3_pass_2_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_4_images_uploaded", 2)

    # Create segments.json
    project_dir = os.path.join(temp_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)

    # Create an image
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    image_path = os.path.join(images_dir, "0001.png")
    with open(image_path, "wb") as f:
        f.write(b"fake_image")

    # Invalidate Step 2
    result = await state_module.invalidate_downstream(project_uuid, 2)
    assert result.value == "step_1_complete"

    # Verify segments.json deleted
    assert not os.path.exists(segments_path)

    # Verify image preserved
    assert os.path.exists(image_path)

    # Verify sub-steps cleared
    sub_state = state_module.get_sub_step_state(project_uuid)
    assert sub_state.get("step_3_pass_1_complete") is None
    assert sub_state.get("step_3_pass_2_complete") is None
    assert sub_state.get("step_4_images_uploaded") is None
    # Step 2 sub-steps preserved
    assert sub_state.get("step_2_call_1_complete") is True
    assert sub_state.get("step_2_call_2_complete") is True


@pytest.mark.asyncio
async def test_invalidate_downstream_step_3(async_client, cleanup_projects, temp_projects_dir):
    """Invalidate from Step 3 resets state to step_2_complete, clears step 4 sub-steps, preserves images."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Cascade Step 3"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Advance to step_4_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/3")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/4")

    # Set up sub-step state
    state_module.set_sub_step_state(project_uuid, "step_2_call_1_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_2_call_2_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_3_pass_1_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_3_pass_2_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_4_images_uploaded", 3)

    # Create segments.json
    project_dir = os.path.join(temp_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)

    # Create images
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    for i in range(1, 4):
        image_path = os.path.join(images_dir, f"{i:04d}.png")
        with open(image_path, "wb") as f:
            f.write(b"fake_image")

    # Invalidate Step 3
    result = await state_module.invalidate_downstream(project_uuid, 3)
    assert result.value == "step_2_complete"

    # Verify segments.json preserved
    assert os.path.exists(segments_path)

    # Verify images preserved
    for i in range(1, 4):
        assert os.path.exists(os.path.join(images_dir, f"{i:04d}.png"))

    # Verify sub-steps
    sub_state = state_module.get_sub_step_state(project_uuid)
    assert sub_state.get("step_3_pass_1_complete") is True
    assert sub_state.get("step_3_pass_2_complete") is True
    assert sub_state.get("step_4_images_uploaded") is None
    assert sub_state.get("step_2_call_1_complete") is True


@pytest.mark.asyncio
async def test_invalidate_downstream_step_4(async_client, cleanup_projects, temp_projects_dir):
    """Invalidate from Step 4 resets state to step_3_complete, preserves all files."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Cascade Step 4"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Advance to step_5_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/3")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/4")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/5")

    # Set up sub-step state
    state_module.set_sub_step_state(project_uuid, "step_2_call_1_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_2_call_2_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_3_pass_1_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_3_pass_2_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_4_images_uploaded", 1)

    # Create files
    project_dir = os.path.join(temp_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    image_path = os.path.join(images_dir, "0001.png")
    with open(image_path, "wb") as f:
        f.write(b"fake_image")

    # Invalidate Step 4
    result = await state_module.invalidate_downstream(project_uuid, 4)
    assert result.value == "step_3_complete"

    # Verify all files preserved
    assert os.path.exists(segments_path)
    assert os.path.exists(image_path)

    # Verify sub-steps preserved
    sub_state = state_module.get_sub_step_state(project_uuid)
    assert sub_state.get("step_2_call_1_complete") is True
    assert sub_state.get("step_2_call_2_complete") is True
    assert sub_state.get("step_3_pass_1_complete") is True
    assert sub_state.get("step_3_pass_2_complete") is True
    assert sub_state.get("step_4_images_uploaded") == 1


@pytest.mark.asyncio
async def test_whisper_mock_respx(async_client, cleanup_projects):
    """Mock OpenAI Whisper API with respx and assert request parameters."""
    # Create a temporary audio file to pass to the transcription function
    import tempfile
    import services.whisper as whisper_module

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        # Write minimal valid MP3 header (silent frame)
        tmp.write(b"\xff\xfb\x90\x00")  # MPEG-1 Layer 3 sync word
        tmp.flush()
        audio_path = tmp.name

    try:
        with respx.mock:
            # Mock OpenAI audio transcriptions endpoint
            route = respx.post("https://api.openai.com/v1/audio/transcriptions").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "text": "Hello world",
                        "words": [
                            {"word": "Hello", "start": 0.0, "end": 0.5},
                            {"word": "world", "start": 0.6, "end": 1.0},
                        ],
                    },
                )
            )

            result = await whisper_module.transcribe_audio(audio_path)
            assert "words" in result, "Result should contain words"
            assert len(result["words"]) == 2, "Should have 2 words"

            # Assert the request was made exactly once
            assert route.called, "OpenAI transcription endpoint should have been called"
            request = route.calls.last.request

            # Parse multipart form to inspect fields
            # httpx Request.content is the raw body bytes
            content = request.content.decode("utf-8", errors="replace")
            assert 'name="model"' in content, "Request should contain model field"
            assert "whisper-1" in content, "Request should contain model='whisper-1'"
            assert 'name="response_format"' in content, "Request should contain response_format field"
            assert "verbose_json" in content, "Request should contain response_format='verbose_json'"
    finally:
        os.remove(audio_path)


@pytest.mark.asyncio
async def test_get_project_not_found(async_client, cleanup_projects):
    """GET /api/v1/projects/{uuid} with non-existent UUID returns 404."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await async_client.get(f"/api/v1/projects/{fake_uuid}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
