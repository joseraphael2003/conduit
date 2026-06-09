import os
import json
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

import routers.video as video_module
import services.ffmpeg as ffmpeg_module
import services.effects as effects_module


@pytest_asyncio.fixture
async def video_projects_dir(temp_projects_dir):
    """Patch video router base dir to use the shared temp directory."""
    original_video_base = video_module.PROJECTS_BASE_DIR
    video_module.PROJECTS_BASE_DIR = temp_projects_dir
    yield temp_projects_dir
    video_module.PROJECTS_BASE_DIR = original_video_base


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint tests: video generation
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_video_generate_success(async_client, cleanup_projects, video_projects_dir):
    """POST video/generate returns 200 with mocked ffmpeg."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Video Gen"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    os.makedirs(conduit_dir, exist_ok=True)

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    for i in range(2):
        img_path = os.path.join(images_dir, f"{i:04d}.png")
        with open(img_path, "wb") as f:
            f.write(b"fake_image")

    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello world.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "image_path": os.path.join(images_dir, "0000.png"),
            },
            {
                "segment_index": 1,
                "script_line": "This is a test.",
                "start_time": 1.0,
                "end_time": 2.0,
                "duration": 1.0,
                "image_path": os.path.join(images_dir, "0001.png"),
            },
        ]
    }
    with open(os.path.join(project_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with open(os.path.join(project_dir, "voiceover.mp3"), "wb") as f:
        f.write(b"\xff\xfb\x90\x00")

    # Advance project state to step_4_complete so video generation can advance to step_5_complete
    for step in range(1, 5):
        await async_client.put(f"/api/v1/projects/{project_uuid}/step/{step}")

    with patch("routers.video.generate_video", return_value=os.path.join(project_dir, "output", "output.mp4")) as mock_gen:
        resp = await async_client.post(
            f"/api/v1/projects/{project_uuid}/video/generate",
            json={"burn_captions": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["output_path"] == "output/output.mp4"
        assert data["duration"] == 2.0
        mock_gen.assert_called_once()


@pytest.mark.asyncio
async def test_video_generate_missing_segments_json(async_client, cleanup_projects, video_projects_dir):
    """POST video/generate returns 404 when segments.json is missing."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Missing Segments"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/video/generate",
        json={"burn_captions": False}
    )
    assert resp.status_code == 404
    assert "segments.json" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_video_generate_empty_segments(async_client, cleanup_projects, video_projects_dir):
    """POST video/generate returns 400 when segments list is empty."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Empty Segments"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    with open(os.path.join(project_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)

    with open(os.path.join(project_dir, "voiceover.mp3"), "wb") as f:
        f.write(b"\xff\xfb\x90\x00")

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/video/generate",
        json={"burn_captions": False}
    )
    assert resp.status_code == 400
    assert "No segments" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_video_generate_missing_images(async_client, cleanup_projects, video_projects_dir):
    """POST video/generate returns 409 when images are missing."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Missing Images"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "image_path": os.path.join(project_dir, "images", "0000.png"),
            }
        ]
    }
    with open(os.path.join(project_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with open(os.path.join(project_dir, "voiceover.mp3"), "wb") as f:
        f.write(b"\xff\xfb\x90\x00")

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/video/generate",
        json={"burn_captions": False}
    )
    assert resp.status_code == 409
    assert "missing images" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_video_generate_missing_voiceover(async_client, cleanup_projects, video_projects_dir):
    """POST video/generate returns 404 when voiceover.mp3 is missing."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Missing Voiceover"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    img_path = os.path.join(images_dir, "0000.png")
    with open(img_path, "wb") as f:
        f.write(b"fake_image")

    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "image_path": img_path,
            }
        ]
    }
    with open(os.path.join(project_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/video/generate",
        json={"burn_captions": False}
    )
    assert resp.status_code == 404
    assert "voiceover" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_video_generate_ffmpeg_failure(async_client, cleanup_projects, video_projects_dir):
    """POST video/generate returns 502 when FFmpeg fails."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "FFmpeg Fail"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    img_path = os.path.join(images_dir, "0000.png")
    with open(img_path, "wb") as f:
        f.write(b"fake_image")

    segments = {
        "segments": [
            {
                "segment_index": 0,
                "script_line": "Hello.",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
                "image_path": img_path,
            }
        ]
    }
    with open(os.path.join(project_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with open(os.path.join(project_dir, "voiceover.mp3"), "wb") as f:
        f.write(b"\xff\xfb\x90\x00")

    # Advance project state to step_4_complete so video generation can advance to step_5_complete
    for step in range(1, 5):
        await async_client.put(f"/api/v1/projects/{project_uuid}/step/{step}")

    with patch("routers.video.generate_video", side_effect=HTTPException(
        status_code=500, detail="FFmpeg failed: some error"
    )):
        resp = await async_client.post(
            f"/api/v1/projects/{project_uuid}/video/generate",
            json={"burn_captions": False}
        )
        assert resp.status_code == 502
        assert "FFmpeg failed" in resp.json()["detail"]


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint tests: video status
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_video_status_idle(async_client, cleanup_projects, video_projects_dir):
    """GET video/status returns idle when no progress."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Status Idle"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    os.makedirs(os.path.join(project_dir, ".conduit"), exist_ok=True)

    segments = {"segments": [{"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0}]}
    with open(os.path.join(project_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"
    assert data["total_segments"] == 1
    assert data["current_segment"] == 0


@pytest.mark.asyncio
async def test_video_status_processing(async_client, cleanup_projects, video_projects_dir):
    """GET video/status returns processing with correct progress."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Status Processing"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    os.makedirs(os.path.join(project_dir, ".conduit"), exist_ok=True)

    segments = {"segments": [
        {"segment_index": 0, "script_line": "A", "start_time": 0.0, "end_time": 1.0, "duration": 1.0},
        {"segment_index": 1, "script_line": "B", "start_time": 1.0, "end_time": 2.0, "duration": 1.0},
        {"segment_index": 2, "script_line": "C", "start_time": 2.0, "end_time": 3.0, "duration": 1.0},
        {"segment_index": 3, "script_line": "D", "start_time": 3.0, "end_time": 4.0, "duration": 1.0},
    ]}
    with open(os.path.join(project_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with open(os.path.join(project_dir, ".conduit", "state.json"), "w", encoding="utf-8") as f:
        json.dump({"video_progress": 50}, f)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processing"
    assert data["current_segment"] == 2
    assert data["total_segments"] == 4


@pytest.mark.asyncio
async def test_video_status_completed(async_client, cleanup_projects, video_projects_dir):
    """GET video/status returns completed when progress is 100."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Status Completed"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    os.makedirs(os.path.join(project_dir, ".conduit"), exist_ok=True)

    segments = {"segments": [
        {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0}
    ]}
    with open(os.path.join(project_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    with open(os.path.join(project_dir, ".conduit", "state.json"), "w", encoding="utf-8") as f:
        json.dump({"video_progress": 100}, f)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["current_segment"] == 1
    assert data["total_segments"] == 1


@pytest.mark.asyncio
async def test_video_status_error(async_client, cleanup_projects, video_projects_dir):
    """GET video/status returns error when video_error is set."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Status Error"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    os.makedirs(os.path.join(project_dir, ".conduit"), exist_ok=True)

    with open(os.path.join(project_dir, ".conduit", "state.json"), "w", encoding="utf-8") as f:
        json.dump({"video_error": "FFmpeg crashed", "video_progress": 50}, f)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert data["message"] == "FFmpeg crashed"


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint tests: download / srt
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_video_logs(async_client, cleanup_projects, video_projects_dir):
    """GET video/logs returns last N lines of ffmpeg log."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Video Logs"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    os.makedirs(os.path.join(project_dir, ".conduit"), exist_ok=True)

    log_path = os.path.join(project_dir, ".conduit", "ffmpeg.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("line1\nline2\nline3\n")

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lines"] == ["line1", "line2", "line3"]

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/logs?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lines"] == ["line2", "line3"]


@pytest.mark.asyncio
async def test_video_logs_not_found(async_client, cleanup_projects, video_projects_dir):
    """GET video/logs returns empty lines when log file is missing."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Video Logs Missing"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    os.makedirs(os.path.join(project_dir, ".conduit"), exist_ok=True)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lines"] == []


@pytest.mark.asyncio
async def test_video_download(async_client, cleanup_projects, video_projects_dir):
    """GET video/download returns MP4 file."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Video Download"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "output.mp4")
    with open(output_path, "wb") as f:
        f.write(b"fake_mp4_content")

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"
    assert resp.content == b"fake_mp4_content"


@pytest.mark.asyncio
async def test_video_download_not_found(async_client, cleanup_projects, video_projects_dir):
    """GET video/download returns 404 when video does not exist."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "No Video"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/download")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_video_srt(async_client, cleanup_projects, video_projects_dir):
    """GET video/srt returns SRT file."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Video SRT"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    srt_path = os.path.join(project_dir, "captions.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/srt")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    assert "Hello" in resp.text


@pytest.mark.asyncio
async def test_video_srt_not_found(async_client, cleanup_projects, video_projects_dir):
    """GET video/srt returns 404 when SRT file does not exist."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "No SRT"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/srt")
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint tests: segment effect
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_segment_effect(async_client, cleanup_projects, temp_projects_dir):
    """PUT segment effect updates effect in segments.json."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Effect Update"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0, "effect": "none"},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.put(
        f"/api/v1/projects/{project_uuid}/segments/0/effect",
        json={"effect": "zoom_in"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment_index"] == 0
    assert data["effect"] == "zoom_in"

    with open(os.path.join(conduit_dir, "segments.json"), "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["segments"][0]["effect"] == "zoom_in"


@pytest.mark.asyncio
async def test_update_segment_effect_invalid(async_client, cleanup_projects, temp_projects_dir):
    """PUT segment effect with invalid effect returns 400."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Effect Invalid"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0, "effect": "none"},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.put(
        f"/api/v1/projects/{project_uuid}/segments/0/effect",
        json={"effect": "spin_around"}
    )
    assert resp.status_code == 400
    assert "Invalid effect" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_segment_effect_not_found(async_client, cleanup_projects, temp_projects_dir):
    """PUT segment effect returns 404 when segments.json is missing."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Effect No File"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    resp = await async_client.put(
        f"/api/v1/projects/{project_uuid}/segments/0/effect",
        json={"effect": "zoom_in"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_segment_effect_index_out_of_bounds(async_client, cleanup_projects, temp_projects_dir):
    """PUT segment effect returns 400 for invalid segment index."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Effect OOB"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    conduit_dir = os.path.join(temp_projects_dir, project_uuid, ".conduit")
    segments = {
        "segments": [
            {"segment_index": 0, "script_line": "Hello.", "start_time": 0.0, "end_time": 1.0, "duration": 1.0, "effect": "none"},
        ]
    }
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump(segments, f)

    resp = await async_client.put(
        f"/api/v1/projects/{project_uuid}/segments/5/effect",
        json={"effect": "zoom_in"}
    )
    assert resp.status_code == 400
    assert "Invalid segment_index" in resp.json()["detail"]


# ──────────────────────────────────────────────────────────────────────────────
# Service tests: effects.py
# ──────────────────────────────────────────────────────────────────────────────

def test_effects_get_params_all():
    """Test get_effect_params returns correct values for all 6 effects."""
    assert effects_module.get_effect_params("none") is None
    assert effects_module.get_effect_params("zoom_in") == {"zoom_start": 1.0, "zoom_end": 1.03, "pan_speed": 0}
    assert effects_module.get_effect_params("zoom_out") == {"zoom_start": 1.03, "zoom_end": 1.0, "pan_speed": 0}
    assert effects_module.get_effect_params("pan_left") == {"zoom_start": 1.0, "zoom_end": 1.0, "pan_speed": 2}
    assert effects_module.get_effect_params("pan_right") == {"zoom_start": 1.0, "zoom_end": 1.0, "pan_speed": -2}
    assert effects_module.get_effect_params("pan_up") == {"zoom_start": 1.0, "zoom_end": 1.0, "pan_speed": 2}
    assert effects_module.get_effect_params("pan_down") == {"zoom_start": 1.0, "zoom_end": 1.0, "pan_speed": -2}


def test_effects_get_params_unknown():
    """Test get_effect_params raises KeyError for unknown effect."""
    with pytest.raises(KeyError):
        effects_module.get_effect_params("spin_around")


def test_effects_validate():
    """Test validate_effect returns correct boolean values."""
    assert effects_module.validate_effect("none") is True
    assert effects_module.validate_effect("zoom_in") is True
    assert effects_module.validate_effect("zoom_out") is True
    assert effects_module.validate_effect("pan_left") is True
    assert effects_module.validate_effect("pan_right") is True
    assert effects_module.validate_effect("pan_up") is True
    assert effects_module.validate_effect("pan_down") is True
    assert effects_module.validate_effect("invalid") is False
    assert effects_module.validate_effect("") is False


def test_effects_random_assign():
    """Test random_assign_effects assigns valid non-none effects."""
    segments = [{"segment_index": i} for i in range(5)]
    assignments = effects_module.random_assign_effects(segments)
    assert len(assignments) == 5
    for i, effect in assignments:
        assert effects_module.validate_effect(effect)
        assert effect != "none"


def test_effects_build_zoompan_filter_zoom_in():
    """Test build_zoompan_filter for zoom_in."""
    f = effects_module.build_zoompan_filter("zoom_in", 2.0, 24)
    assert "zoompan" in f
    assert "d=48" in f
    assert "s=1920x1080" in f
    assert "fps=24" in f
    assert "z='1.0+on/48*0.03'" in f
    assert "x='iw/2-(iw/zoom/2)'" in f
    assert "y='ih/2-(ih/zoom/2)'" in f


def test_effects_build_zoompan_filter_zoom_out():
    """Test build_zoompan_filter for zoom_out."""
    f = effects_module.build_zoompan_filter("zoom_out", 1.0, 30)
    assert "zoompan" in f
    assert "d=30" in f
    assert "s=1920x1080" in f
    assert "fps=30" in f
    assert "z='1.03+on/30*-0.03'" in f
    assert "x='iw/2-(iw/zoom/2)'" in f
    assert "y='ih/2-(ih/zoom/2)'" in f


def test_effects_build_zoompan_filter_pan_left():
    """Test build_zoompan_filter for pan_left."""
    f = effects_module.build_zoompan_filter("pan_left", 2.0, 24)
    assert f == "zoompan=d=48:s=1920x1080:fps=24:z=1:x='iw/2-(iw/zoom/2)+on*2':y='ih/2-(ih/zoom/2)'"


def test_effects_build_zoompan_filter_pan_right():
    """Test build_zoompan_filter for pan_right."""
    f = effects_module.build_zoompan_filter("pan_right", 2.0, 24)
    assert f == "zoompan=d=48:s=1920x1080:fps=24:z=1:x='iw/2-(iw/zoom/2)+on*-2':y='ih/2-(ih/zoom/2)'"


def test_effects_build_zoompan_filter_pan_up():
    """Test build_zoompan_filter for pan_up."""
    f = effects_module.build_zoompan_filter("pan_up", 2.0, 24)
    assert f == "zoompan=d=48:s=1920x1080:fps=24:z=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+on*2'"


def test_effects_build_zoompan_filter_pan_down():
    """Test build_zoompan_filter for pan_down."""
    f = effects_module.build_zoompan_filter("pan_down", 2.0, 24)
    assert f == "zoompan=d=48:s=1920x1080:fps=24:z=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+on*-2'"


def test_effects_build_zoompan_filter_none_raises():
    """Test build_zoompan_filter raises ValueError for none effect."""
    with pytest.raises(ValueError, match='Cannot build zoompan filter for "none" effect'):
        effects_module.build_zoompan_filter("none", 2.0, 24)


def test_effects_build_zoompan_filter_unknown():
    """Test build_zoompan_filter raises KeyError for unknown effect."""
    with pytest.raises(KeyError):
        effects_module.build_zoompan_filter("spin_around", 2.0, 24)


# ──────────────────────────────────────────────────────────────────────────────
# Service tests: ffmpeg.py
# ──────────────────────────────────────────────────────────────────────────────

def test_ffmpeg_run_ffmpeg_success():
    """Test _run_ffmpeg calls subprocess.run with correct arguments."""
    with patch("services.ffmpeg.subprocess.run") as mock_run:
        ffmpeg_module._run_ffmpeg(["ffmpeg", "-i", "input.mp4", "output.mp4"])
        mock_run.assert_called_once_with(
            ["ffmpeg", "-i", "input.mp4", "output.mp4"],
            capture_output=True,
            text=True,
            check=True,
        )


def test_ffmpeg_run_ffmpeg_failure():
    """Test _run_ffmpeg raises HTTPException on subprocess failure."""
    from subprocess import CalledProcessError
    with patch("services.ffmpeg.subprocess.run") as mock_run:
        mock_run.side_effect = CalledProcessError(
            returncode=1,
            cmd=["ffmpeg"],
            stderr="some error",
            output="",
        )
        with pytest.raises(HTTPException) as exc_info:
            ffmpeg_module._run_ffmpeg(["ffmpeg", "-i", "input.mp4", "output.mp4"])
        assert exc_info.value.status_code == 500
        assert "FFmpeg failed" in exc_info.value.detail


def test_ffmpeg_generate_segment_clip_none():
    """Test generate_segment_clip builds correct command for none effect."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.generate_segment_clip("img.png", 2.0, "none", "out.mp4")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-loop" in cmd
        assert "1" in cmd
        assert "-i" in cmd
        assert "img.png" in cmd
        assert "-t" in cmd
        assert "2.0" in cmd
        assert "out.mp4" in cmd


def test_ffmpeg_generate_segment_clip_zoom_in():
    """Test generate_segment_clip builds correct command for zoom_in."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.generate_segment_clip("img.png", 1.0, "zoom_in", "out.mp4")
        cmd = mock_run.call_args[0][0]
        vf_arg = _get_vf_arg(cmd)
        assert "zoompan" in vf_arg
        assert "z='1.0+on/24*0.03'" in vf_arg
        assert "s=1920x1080" in vf_arg
        assert "scale=1920" not in vf_arg


def test_ffmpeg_generate_segment_clip_zoom_out():
    """Test generate_segment_clip builds correct command for zoom_out."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.generate_segment_clip("img.png", 1.0, "zoom_out", "out.mp4")
        cmd = mock_run.call_args[0][0]
        vf_arg = _get_vf_arg(cmd)
        assert "zoompan" in vf_arg
        assert "z='1.03+on/24*-0.03'" in vf_arg
        assert "s=1920x1080" in vf_arg
        assert "scale=1920" not in vf_arg


def test_ffmpeg_generate_segment_clip_pan_left():
    """Test generate_segment_clip builds correct command for pan_left."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.generate_segment_clip("img.png", 1.0, "pan_left", "out.mp4")
        cmd = mock_run.call_args[0][0]
        vf_arg = _get_vf_arg(cmd)
        assert "zoompan" in vf_arg
        assert "x='iw/2-(iw/zoom/2)+on*2'" in vf_arg
        assert "s=1920x1080" in vf_arg
        assert "scale=1920" not in vf_arg


def test_ffmpeg_generate_segment_clip_pan_right():
    """Test generate_segment_clip builds correct command for pan_right."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.generate_segment_clip("img.png", 1.0, "pan_right", "out.mp4")
        cmd = mock_run.call_args[0][0]
        vf_arg = _get_vf_arg(cmd)
        assert "zoompan" in vf_arg
        assert "x='iw/2-(iw/zoom/2)+on*-2'" in vf_arg
        assert "s=1920x1080" in vf_arg
        assert "scale=1920" not in vf_arg


def test_ffmpeg_generate_segment_clip_pan_up():
    """Test generate_segment_clip builds correct command for pan_up."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.generate_segment_clip("img.png", 1.0, "pan_up", "out.mp4")
        cmd = mock_run.call_args[0][0]
        vf_arg = _get_vf_arg(cmd)
        assert "zoompan" in vf_arg
        assert "y='ih/2-(ih/zoom/2)+on*2'" in vf_arg
        assert "s=1920x1080" in vf_arg
        assert "scale=1920" not in vf_arg


def test_ffmpeg_generate_segment_clip_pan_down():
    """Test generate_segment_clip builds correct command for pan_down."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.generate_segment_clip("img.png", 1.0, "pan_down", "out.mp4")
        cmd = mock_run.call_args[0][0]
        vf_arg = _get_vf_arg(cmd)
        assert "zoompan" in vf_arg
        assert "y='ih/2-(ih/zoom/2)+on*-2'" in vf_arg
        assert "s=1920x1080" in vf_arg
        assert "scale=1920" not in vf_arg


def test_ffmpeg_generate_segment_clip_unknown():
    """Test generate_segment_clip raises HTTPException for unknown effect."""
    with patch("services.ffmpeg._run_ffmpeg"):
        with pytest.raises(HTTPException) as exc_info:
            ffmpeg_module.generate_segment_clip("img.png", 1.0, "spin_around", "out.mp4")
        assert exc_info.value.status_code == 400
        assert "Unknown effect" in exc_info.value.detail


def test_ffmpeg_concat_segments(tmp_path):
    """Test concat_segments creates ffconcat file and calls ffmpeg."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        clips = ["clip1.mp4", "clip2.mp4"]
        concat_path = str(tmp_path / "concat.txt")
        result = ffmpeg_module.concat_segments(clips, concat_path)
        assert result == str(tmp_path / "concat.mp4")
        assert os.path.exists(concat_path)
        with open(concat_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "ffconcat version 1.0" in content
        assert "clip1.mp4" in content
        assert "clip2.mp4" in content
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-f" in cmd
        assert "concat" in cmd


def test_ffmpeg_mix_audio():
    """Test mix_audio calls ffmpeg with correct audio options."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.mix_audio("video.mp4", "audio.mp3", "out.mp4")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-c:v" in cmd
        assert "copy" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "-shortest" in cmd


def test_ffmpeg_burn_captions():
    """Test burn_captions calls ffmpeg with subtitles filter."""
    with patch("services.ffmpeg._run_ffmpeg") as mock_run:
        ffmpeg_module.burn_captions("video.mp4", "subs.srt", "out.mp4")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-vf" in cmd
        vf_arg = _get_vf_arg(cmd)
        assert "subtitles" in vf_arg


@pytest.mark.asyncio
async def test_ffmpeg_generate_video(tmp_path):
    """Test generate_video orchestrates the pipeline correctly."""
    project_dir = str(tmp_path / "project")
    os.makedirs(project_dir, exist_ok=True)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    img_path = os.path.join(images_dir, "img.png")
    with open(img_path, "wb") as f:
        f.write(b"fake")

    temp_dir = str(tmp_path / "temp")
    os.makedirs(temp_dir, exist_ok=True)

    segments = [
        {"image_path": img_path, "duration": 1.0, "effect": "none"},
        {"image_path": img_path, "duration": 2.0, "effect": "zoom_in"},
    ]
    voiceover_path = os.path.join(project_dir, "voice.mp3")
    with open(voiceover_path, "wb") as f:
        f.write(b"\xff\xfb\x90\x00")

    with patch("services.ffmpeg.tempfile.mkdtemp", return_value=temp_dir), \
         patch("services.ffmpeg.generate_segment_clip") as mock_clip, \
         patch("services.ffmpeg.concat_segments", return_value=os.path.join(temp_dir, "concat.mp4")) as mock_concat, \
         patch("services.ffmpeg.mix_audio") as mock_mix, \
         patch("services.ffmpeg._write_progress") as mock_progress, \
         patch("services.ffmpeg.shutil.copy") as mock_copy, \
         patch("services.ffmpeg.shutil.rmtree") as mock_rmtree:

        result = await ffmpeg_module.generate_video(
            project_dir, segments, voiceover_path, should_burn_captions=False
        )

        assert mock_clip.call_count == 2
        assert mock_concat.called
        assert mock_mix.called
        assert mock_copy.called
        assert mock_progress.called
        assert result == os.path.join(project_dir, "output", "output.mp4")


@pytest.mark.asyncio
async def test_ffmpeg_generate_video_with_captions(tmp_path):
    """Test generate_video burns captions when requested."""
    project_dir = str(tmp_path / "project")
    os.makedirs(project_dir, exist_ok=True)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    img_path = os.path.join(images_dir, "img.png")
    with open(img_path, "wb") as f:
        f.write(b"fake")

    srt_path = os.path.join(project_dir, "captions.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

    temp_dir = str(tmp_path / "temp")
    os.makedirs(temp_dir, exist_ok=True)

    segments = [{"image_path": img_path, "duration": 1.0, "effect": "none"}]
    voiceover_path = os.path.join(project_dir, "voice.mp3")
    with open(voiceover_path, "wb") as f:
        f.write(b"\xff\xfb\x90\x00")

    with patch("services.ffmpeg.tempfile.mkdtemp", return_value=temp_dir), \
         patch("services.ffmpeg.generate_segment_clip"), \
         patch("services.ffmpeg.concat_segments", return_value=os.path.join(temp_dir, "concat.mp4")), \
         patch("services.ffmpeg.mix_audio"), \
         patch("services.ffmpeg.burn_captions") as mock_burn, \
         patch("services.ffmpeg._write_progress"), \
         patch("services.ffmpeg.shutil.copy") as mock_copy, \
         patch("services.ffmpeg.shutil.rmtree"):

        result = await ffmpeg_module.generate_video(
            project_dir, segments, voiceover_path, should_burn_captions=True
        )

        assert mock_burn.called
        assert mock_copy.called
        assert result == os.path.join(project_dir, "output", "output.mp4")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_vf_arg(cmd):
    """Extract the -vf argument value from an ffmpeg command list."""
    for i, arg in enumerate(cmd):
        if arg == "-vf" and i + 1 < len(cmd):
            return cmd[i + 1]
    raise ValueError("No -vf argument found in command")


# ──────────────────────────────────────────────────────────────────────────────
# 0.8.5 hardening regression tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_write_progress_writes_valid_timestamp(tmp_path):
    """Issue 1: _write_progress must write video_progress + an ISO updated_at
    without raising (regression for the datetime import bug)."""
    from datetime import datetime

    project_dir = str(tmp_path / "project")
    conduit_dir = os.path.join(project_dir, ".conduit")
    os.makedirs(conduit_dir, exist_ok=True)
    state_path = os.path.join(conduit_dir, "state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"state": "step_4_complete"}, f)

    # Must not raise (the bug raised AttributeError/NameError here).
    ffmpeg_module._write_progress(project_dir, 50)

    with open(state_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["video_progress"] == 50
    # updated_at must be a valid ISO 8601 timestamp.
    datetime.fromisoformat(data["updated_at"])


@pytest.mark.asyncio
async def test_video_status_counts_conduit_segments(async_client, cleanup_projects, video_projects_dir):
    """Issue 5: get_video_status must count segments from .conduit/segments.json."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Status Count"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    os.makedirs(conduit_dir, exist_ok=True)
    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": [{"segment_index": i} for i in range(3)]}, f)

    resp = await async_client.get(f"/api/v1/projects/{project_uuid}/video/status")
    assert resp.status_code == 200
    assert resp.json()["total_segments"] == 3


def test_ffmpeg_path_honors_env(monkeypatch):
    """Issue 6: FFMPEG_PATH reads CONDUIT_FFMPEG_PATH, defaulting to 'ffmpeg'."""
    import importlib

    monkeypatch.setenv("CONDUIT_FFMPEG_PATH", "/custom/path/ffmpeg")
    importlib.reload(ffmpeg_module)
    assert ffmpeg_module.FFMPEG_PATH == "/custom/path/ffmpeg"

    monkeypatch.delenv("CONDUIT_FFMPEG_PATH", raising=False)
    importlib.reload(ffmpeg_module)
    assert ffmpeg_module.FFMPEG_PATH == "ffmpeg"


@pytest.mark.asyncio
async def test_video_generate_finds_wav_voiceover(async_client, cleanup_projects, video_projects_dir):
    """Issue 4: video generation resolves a .wav voiceover (not only .mp3)."""
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Wav Voiceover"})
    assert create_resp.status_code == 201
    project_uuid = create_resp.json()["uuid"]

    project_dir = os.path.join(video_projects_dir, project_uuid)
    conduit_dir = os.path.join(project_dir, ".conduit")
    os.makedirs(conduit_dir, exist_ok=True)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    img_path = os.path.join(images_dir, "0000.png")
    with open(img_path, "wb") as f:
        f.write(b"fake_image")

    with open(os.path.join(conduit_dir, "segments.json"), "w", encoding="utf-8") as f:
        json.dump({"segments": [{
            "segment_index": 0, "script_line": "Hi.", "start_time": 0.0,
            "end_time": 1.0, "duration": 1.0, "image_path": img_path,
        }]}, f)

    # Only a .wav voiceover exists (no .mp3).
    with open(os.path.join(project_dir, "voiceover.wav"), "wb") as f:
        f.write(b"RIFF\x00\x00\x00\x00WAVE")

    for step in range(1, 5):
        await async_client.put(f"/api/v1/projects/{project_uuid}/step/{step}")

    with patch("routers.video.generate_video", return_value=os.path.join(project_dir, "output", "output.mp4")) as mock_gen:
        resp = await async_client.post(
            f"/api/v1/projects/{project_uuid}/video/generate",
            json={"burn_captions": False},
        )
        assert resp.status_code == 200, f"got {resp.status_code}: {resp.text}"
        mock_gen.assert_called_once()
        # The resolved voiceover path passed to generate_video must be the .wav.
        passed_voiceover = mock_gen.call_args[0][2]
        assert passed_voiceover.endswith("voiceover.wav")
