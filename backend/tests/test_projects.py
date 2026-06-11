import os
import json
import pytest
import httpx
import respx
from openai import APIStatusError

# We import the app module for test-client setup
from main import app
import models.database
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
async def test_delete_project_removes_folder_and_row(async_client, cleanup_projects, temp_projects_dir):
    """DELETE removes both filesystem folder and DB row."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Delete Test"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Verify folder exists before
    project_dir = os.path.join(temp_projects_dir, project_uuid)
    assert os.path.exists(project_dir), "Project folder should exist before delete"

    # Delete
    response = await async_client.delete(f"/api/v1/projects/{project_uuid}")
    assert response.status_code == 204

    # Verify DB row gone
    db = await models.database.get_db()
    try:
        cursor = await db.execute("SELECT count(*) FROM projects WHERE uuid = ?", (project_uuid,))
        count = (await cursor.fetchone())[0]
    finally:
        await db.close()
    assert count == 0, "DB row should be deleted"

    # Verify folder gone
    assert not os.path.exists(project_dir), "Project folder should be deleted"

    # Verify GET returns 404
    get_response = await async_client.get(f"/api/v1/projects/{project_uuid}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_rmtree_failure_no_orphan(async_client, cleanup_projects, temp_projects_dir, monkeypatch):
    """Failed rmtree leaves DB row and folder intact (no orphan)."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Rmtree Fail"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Monkeypatch shutil.rmtree to raise
    def fake_rmtree(path):
        raise OSError("Permission denied")

    import routers.projects as projects_module
    monkeypatch.setattr(projects_module.shutil, "rmtree", fake_rmtree)

    # Delete should return 500
    response = await async_client.delete(f"/api/v1/projects/{project_uuid}")
    assert response.status_code == 500

    # Verify DB row STILL present
    db = await models.database.get_db()
    try:
        cursor = await db.execute("SELECT count(*) FROM projects WHERE uuid = ?", (project_uuid,))
        count = (await cursor.fetchone())[0]
    finally:
        await db.close()
    assert count == 1, "DB row should still exist (no orphan)"

    # Verify folder STILL present
    project_dir = os.path.join(temp_projects_dir, project_uuid)
    assert os.path.exists(project_dir), "Folder should still exist (no orphan)"


@pytest.mark.asyncio
async def test_delete_project_not_found(async_client):
    """DELETE non-existent UUID returns 404."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await async_client.delete(f"/api/v1/projects/{fake_uuid}")
    assert response.status_code == 404


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
    state_module.set_sub_step_state(project_uuid, "step_2_timeline_complete", True)
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
    # Step 2 sub-steps: call-1 and timeline preserved; call-2 cleared (must rerun after version edit)
    assert sub_state.get("step_2_call_1_complete") is True
    assert sub_state.get("step_2_timeline_complete") is True
    assert sub_state.get("step_2_call_2_complete") is None


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
async def test_whisper_retry_success(async_client, cleanup_projects):
    """Mock Whisper 500→500→200. Assert transcription succeeds on 3rd attempt."""
    import tempfile
    import services.whisper as whisper_module

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(b"\xff\xfb\x90\x00")
        tmp.flush()
        audio_path = tmp.name

    try:
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return httpx.Response(500, json={"error": "Internal Server Error"})
            return httpx.Response(
                200,
                json={
                    "text": "Hello world",
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5},
                        {"word": "world", "start": 0.6, "end": 1.0},
                    ],
                },
            )

        with respx.mock:
            route = respx.post("https://api.openai.com/v1/audio/transcriptions").mock(
                side_effect=side_effect
            )
            result = await whisper_module.transcribe_audio(audio_path)
            assert "words" in result
            assert len(result["words"]) == 2
            assert call_count == 3
            assert route.call_count == 3
    finally:
        os.remove(audio_path)


@pytest.mark.asyncio
async def test_whisper_retry_failure(async_client, cleanup_projects):
    """Mock Whisper 500×4. Assert transcription fails with specific error after 3 retries."""
    import tempfile
    import services.whisper as whisper_module

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(b"\xff\xfb\x90\x00")
        tmp.flush()
        audio_path = tmp.name

    try:
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, json={"error": "Internal Server Error"})

        with respx.mock:
            route = respx.post("https://api.openai.com/v1/audio/transcriptions").mock(
                side_effect=side_effect
            )
            with pytest.raises(APIStatusError) as exc_info:
                await whisper_module.transcribe_audio(audio_path)
            assert call_count == 4  # initial + 3 retries
            assert route.call_count == 4
            assert exc_info.value.status_code == 500
    finally:
        os.remove(audio_path)


@pytest.mark.asyncio
async def test_get_project_not_found(async_client, cleanup_projects):
    """GET /api/v1/projects/{uuid} with non-existent UUID returns 404."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await async_client.get(f"/api/v1/projects/{fake_uuid}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_voiceover_reupload_preserves_outputs(async_client, cleanup_projects, temp_projects_dir):
    """Re-uploading voiceover preserves captions.srt and words.json, clears downstream segments.json."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Reupload Test"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    fake_mp3 = b"\xff\xfb\x90\x00"

    # First upload with mocked Whisper
    with respx.mock:
        respx.post("https://api.openai.com/v1/audio/transcriptions").mock(
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
        resp1 = await async_client.post(
            f"/api/v1/projects/{project_uuid}/voiceover",
            files={"file": ("voiceover.mp3", fake_mp3, "audio/mpeg")},
        )
        assert resp1.status_code == 202, f"First upload failed: {resp1.text}"

    # Verify state after first upload
    state_resp1 = await async_client.get(f"/api/v1/projects/{project_uuid}")
    assert state_resp1.json()["state"] == "step_1_complete"

    # Pre-stage downstream files
    project_dir = os.path.join(temp_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    os.makedirs(conduit_dir, exist_ok=True)
    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)

    state_module.set_sub_step_state(project_uuid, "step_2_call_1_complete", True)

    # Re-upload with mocked Whisper
    with respx.mock:
        respx.post("https://api.openai.com/v1/audio/transcriptions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "text": "Hello again",
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5},
                        {"word": "again", "start": 0.6, "end": 1.0},
                    ],
                },
            )
        )
        resp2 = await async_client.post(
            f"/api/v1/projects/{project_uuid}/voiceover",
            files={"file": ("voiceover.mp3", fake_mp3, "audio/mpeg")},
        )
        assert resp2.status_code == 202, f"Re-upload failed: {resp2.text}"

    # Assert after second upload
    captions_path = os.path.join(project_dir, "captions.srt")
    words_path = os.path.join(conduit_dir, "words.json")
    assert os.path.exists(captions_path), "captions.srt should be preserved after re-upload"
    assert os.path.exists(words_path), ".conduit/words.json should be preserved after re-upload"
    assert not os.path.exists(segments_path), ".conduit/segments.json should be deleted (downstream cleared)"
    state_resp2 = await async_client.get(f"/api/v1/projects/{project_uuid}")
    assert state_resp2.json()["state"] == "step_1_complete"


@pytest.mark.asyncio
async def test_invalidate_downstream_step_1(async_client, cleanup_projects, temp_projects_dir):
    """Invalidate from Step 1 resets state to created, deletes captions.srt and segments.json, preserves images, clears sub-steps."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Cascade Step 1"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Advance to step_1_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")

    # Set up sub-step state
    state_module.set_sub_step_state(project_uuid, "step_2_call_1_complete", True)
    state_module.set_sub_step_state(project_uuid, "step_3_pass_1_complete", True)

    # Stage files
    project_dir = os.path.join(temp_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    os.makedirs(conduit_dir, exist_ok=True)

    captions_path = os.path.join(project_dir, "captions.srt")
    with open(captions_path, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

    words_path = os.path.join(conduit_dir, "words.json")
    with open(words_path, "w", encoding="utf-8") as f:
        json.dump({"words": []}, f)

    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    image_path = os.path.join(images_dir, "0001.png")
    with open(image_path, "wb") as f:
        f.write(b"fake_image")

    # Invalidate Step 1
    result = await state_module.invalidate_downstream(project_uuid, 1)
    assert result.value == "created"

    # Verify captions.srt deleted
    assert not os.path.exists(captions_path)

    # Verify segments.json deleted
    assert not os.path.exists(segments_path)

    # Verify image preserved
    assert os.path.exists(image_path)

    # Verify sub-steps cleared
    sub_state = state_module.get_sub_step_state(project_uuid)
    assert sub_state.get("step_2_call_1_complete") is None
    assert sub_state.get("step_3_pass_1_complete") is None


# ──────────────────────────────────────────────────────────────────────────────
# 0.8.5 hardening regression tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chunked_transcription_applies_offsets(async_client, cleanup_projects, temp_projects_dir, monkeypatch):
    """Issue 2: >25 MB audio is chunked; each chunk's words must be shifted by
    its original-audio offset so timestamps stay monotonic (no rewind)."""
    import routers.projects as projects_mod

    create_resp = await async_client.post("/api/v1/projects", json={"name": "Chunked"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Force the >25 MB branch (gate at projects.py: os.path.getsize > 25_000_000).
    real_getsize = os.path.getsize
    monkeypatch.setattr(
        "routers.projects.os.path.getsize",
        lambda p: 25_000_001 if str(p).endswith(("voiceover.mp3", "voiceover.wav", "voiceover.m4a")) else real_getsize(p),
    )
    # Two chunks at original-audio offsets 0.0s and 30.0s (fake paths; transcribe is mocked).
    monkeypatch.setattr(
        "routers.projects.chunk_audio",
        lambda p: [("/fake/chunk0.wav", 0.0), ("/fake/chunk1.wav", 30.0)],
    )

    async def fake_transcribe(_path):
        # Fresh dict each call; chunk-relative timestamps (both start near 0).
        return {"words": [
            {"word": "a", "start": 0.0, "end": 0.5},
            {"word": "b", "start": 1.0, "end": 1.5},
        ]}

    monkeypatch.setattr("routers.projects.transcribe_audio", fake_transcribe)

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/voiceover",
        files={"file": ("voiceover.mp3", b"\xff\xfb\x90\x00", "audio/mpeg")},
    )
    assert resp.status_code == 202, f"got {resp.status_code}: {resp.text}"
    # Issue 8: synchronous completion is reflected in the response.
    body = resp.json()
    assert body["processing"] is False
    assert body["message"] == "Audio uploaded and transcribed."

    # Read the persisted words and verify chunk-2 timestamps were offset by 30s.
    words_path = os.path.join(temp_projects_dir, project_uuid, ".conduit", "words.json")
    with open(words_path, "r", encoding="utf-8") as f:
        words = json.load(f)["words"]
    assert len(words) == 4
    assert words[0]["start"] == 0.0 and words[1]["end"] == 1.5      # chunk 1 unchanged
    assert words[2]["start"] == 30.0 and words[2]["end"] == 30.5    # chunk 2 + 30s offset
    assert words[3]["start"] == 31.0 and words[3]["end"] == 31.5
    # No rewind: chunk-2 first word starts at/after chunk-1 last word's end.
    assert words[2]["start"] >= words[1]["end"]


@pytest.mark.asyncio
async def test_global_exception_handler_returns_detail():
    """Issue 7: the global 500 handler returns {"detail": ...} (not {"error": ...})."""
    from main import global_exception_handler

    resp = await global_exception_handler(None, Exception("boom"))
    assert resp.status_code == 500
    payload = json.loads(resp.body)
    assert "detail" in payload
    assert "error" not in payload


@pytest.mark.asyncio
async def test_invalidate_downstream_step_4_clears_video_state_and_output(async_client, cleanup_projects, temp_projects_dir):
    """Invalidate from Step 4 (or at step 5) clears video_progress, video_error, and output.mp4."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Video Cleanup"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    # Advance all the way to step_5_complete
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/1")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/2")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/3")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/4")
    await async_client.put(f"/api/v1/projects/{project_uuid}/step/5")

    # Stage video state and output file
    state_module.set_sub_step_state(project_uuid, "video_progress", 100)
    state_module.set_sub_step_state(project_uuid, "video_error", "some error")

    project_dir = os.path.join(temp_projects_dir, project_uuid)
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "output.mp4")
    with open(output_path, "wb") as f:
        f.write(b"fake_video")

    # Also stage segments.json and images (should be preserved)
    conduit_dir = os.path.join(project_dir, ".conduit")
    segments_path = os.path.join(conduit_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    image_path = os.path.join(images_dir, "0001.png")
    with open(image_path, "wb") as f:
        f.write(b"fake_image")

    # Invalidate from Step 4
    result = await state_module.invalidate_downstream(project_uuid, 4)
    assert result.value == "step_3_complete"

    # Video file deleted
    assert not os.path.exists(output_path)
    # Segments and images preserved
    assert os.path.exists(segments_path)
    assert os.path.exists(image_path)

    # video_progress and video_error cleared from state.json
    state_json_path = os.path.join(conduit_dir, "state.json")
    with open(state_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "video_progress" not in data
    assert "video_error" not in data
