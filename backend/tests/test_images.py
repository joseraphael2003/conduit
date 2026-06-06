import os
import json
import io
import pytest
import pytest_asyncio
from PIL import Image
from httpx import AsyncClient

from main import app

# Patch projects base dir before importing images module
import routers.images as images_module
import routers.projects as projects_module

_original_images_base = images_module.PROJECTS_BASE_DIR


@pytest.fixture
def temp_images_dir(temp_projects_dir):
    """Patch images module to use temp projects dir."""
    images_module.PROJECTS_BASE_DIR = temp_projects_dir
    yield temp_projects_dir
    images_module.PROJECTS_BASE_DIR = _original_images_base


def create_test_png(width: int, height: int, mode: str = "RGB") -> bytes:
    """Create a test PNG image in memory."""
    image = Image.new(mode, (width, height), color=(255, 0, 0) if mode == "RGB" else (255, 0, 0, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_upload_image_success(async_client, temp_images_dir, cleanup_projects):
    """POST /api/v1/projects/{uuid}/images/1 with valid PNG returns 200."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create a segments.json file
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    segments_data = {
        "segments": [
            {
                "segment_index": 1,
                "script_line": "Hello world",
                "start_time": 0.0,
                "end_time": 1.0,
                "duration": 1.0,
            }
        ]
    }
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f)

    # Upload a valid 1920x1080 PNG
    png_data = create_test_png(1920, 1080)
    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/images/1",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["segment_index"] == 1
    assert "image_path" in data
    assert data["image_path"].endswith("images/0001.png") or data["image_path"].endswith("images\\0001.png")

    # Verify file was saved
    assert os.path.exists(data["image_path"])

    # Verify segments.json was updated
    with open(segments_path, "r", encoding="utf-8") as f:
        updated = json.load(f)
    assert updated["segments"][0]["image_path"] == data["image_path"]


@pytest.mark.asyncio
async def test_upload_image_non_png(async_client, temp_images_dir, cleanup_projects):
    """POST with non-PNG returns 400 with detail 'PNG only'."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create segments.json
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    segments_data = {"segments": [{"segment_index": 1, "script_line": "Test"}]}
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f)

    # Upload a JPG (disguised as PNG in filename but wrong content type)
    jpg_image = Image.new("RGB", (100, 100), color=(255, 0, 0))
    jpg_buffer = io.BytesIO()
    jpg_image.save(jpg_buffer, format="JPEG")
    jpg_data = jpg_buffer.getvalue()

    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/images/1",
        files={"file": ("test.jpg", io.BytesIO(jpg_data), "image/jpeg")},
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert response.json()["detail"] == "PNG only"


@pytest.mark.asyncio
async def test_upload_image_wrong_aspect_ratio(async_client, temp_images_dir, cleanup_projects):
    """POST with non-16:9 PNG returns 400 with detail 'Image must be 16:9 aspect ratio'."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create segments.json
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    segments_data = {"segments": [{"segment_index": 1, "script_line": "Test"}]}
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f)

    # Upload a 1000x1000 PNG (1:1 aspect ratio)
    png_data = create_test_png(1000, 1000)
    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/images/1",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert response.json()["detail"] == "Image must be 16:9 aspect ratio"


@pytest.mark.asyncio
async def test_upload_image_rgba_conversion(async_client, temp_images_dir, cleanup_projects):
    """POST with RGBA PNG auto-converts to RGB and saves successfully."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create segments.json
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    segments_data = {"segments": [{"segment_index": 1, "script_line": "Test"}]}
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f)

    # Upload a 1920x1080 RGBA PNG
    png_data = create_test_png(1920, 1080, mode="RGBA")
    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/images/1",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["segment_index"] == 1

    # Verify the saved image is RGB (not RGBA)
    from PIL import Image
    saved_image = Image.open(data["image_path"])
    assert saved_image.mode == "RGB"


@pytest.mark.asyncio
async def test_upload_image_low_resolution(async_client, temp_images_dir, cleanup_projects):
    """POST with low resolution PNG still succeeds but warns."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create segments.json
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    segments_data = {"segments": [{"segment_index": 1, "script_line": "Test"}]}
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f)

    # Upload a 1600x900 PNG (16:9 but below minimum)
    png_data = create_test_png(1600, 900)
    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/images/1",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["segment_index"] == 1


@pytest.mark.asyncio
async def test_get_image(async_client, temp_images_dir, cleanup_projects):
    """GET /api/v1/projects/{uuid}/images/1 returns the image file."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create segments.json
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    segments_data = {"segments": [{"segment_index": 1, "script_line": "Test"}]}
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f)

    # Upload a valid PNG
    png_data = create_test_png(1920, 1080)
    upload_resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/images/1",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert upload_resp.status_code == 200

    # Get the image
    get_resp = await async_client.get(f"/api/v1/projects/{project_uuid}/images/1")
    assert get_resp.status_code == 200, f"Expected 200, got {get_resp.status_code}"
    assert get_resp.headers.get("content-type") == "image/png"
    assert len(get_resp.content) > 0


@pytest.mark.asyncio
async def test_get_image_not_found(async_client, temp_images_dir, cleanup_projects):
    """GET /api/v1/projects/{uuid}/images/1 with missing image returns 404."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    response = await async_client.get(f"/api/v1/projects/{project_uuid}/images/1")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_upload_image_project_not_found(async_client, temp_images_dir, cleanup_projects):
    """POST with non-existent project returns 404."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    png_data = create_test_png(1920, 1080)
    response = await async_client.post(
        f"/api/v1/projects/{fake_uuid}/images/1",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    assert response.json()["detail"] == "Project not found"


@pytest.mark.asyncio
async def test_upload_image_segment_not_found(async_client, temp_images_dir, cleanup_projects):
    """POST with non-existent segment index returns 404."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create segments.json with only segment 1
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    segments_data = {"segments": [{"segment_index": 1, "script_line": "Test"}]}
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f)

    # Try to upload to segment 2
    png_data = create_test_png(1920, 1080)
    response = await async_client.post(
        f"/api/v1/projects/{project_uuid}/images/2",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    assert response.json()["detail"] == "Segment 2 not found"


@pytest.mark.asyncio
async def test_get_images_status(async_client, temp_images_dir, cleanup_projects):
    """GET /api/v1/projects/{uuid}/images/status returns correct map for all segments."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create segments.json with segments 1 and 2
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    segments_data = {
        "segments": [
            {"segment_index": 1, "script_line": "Hello"},
            {"segment_index": 2, "script_line": "World"},
        ]
    }
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments_data, f)

    # Upload image only for segment 1
    png_data = create_test_png(1920, 1080)
    upload_resp = await async_client.post(
        f"/api/v1/projects/{project_uuid}/images/1",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert upload_resp.status_code == 200

    # Get status
    status_resp = await async_client.get(f"/api/v1/projects/{project_uuid}/images/status")
    assert status_resp.status_code == 200, f"Expected 200, got {status_resp.status_code}: {status_resp.text}"
    data = status_resp.json()
    assert data == {"1": True, "2": False}


@pytest.mark.asyncio
async def test_get_images_status_project_not_found(async_client, temp_images_dir, cleanup_projects):
    """GET /api/v1/projects/{uuid}/images/status with missing project returns 404."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = await async_client.get(f"/api/v1/projects/{fake_uuid}/images/status")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    assert response.json()["detail"] == "Project not found"


@pytest.mark.asyncio
async def test_get_images_status_segments_not_found(async_client, temp_images_dir, cleanup_projects):
    """GET /api/v1/projects/{uuid}/images/status with missing segments.json returns 404."""
    # Create a project (no segments.json)
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    response = await async_client.get(f"/api/v1/projects/{project_uuid}/images/status")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    assert response.json()["detail"] == "Project segments not found"


@pytest.mark.asyncio
async def test_get_images_status_empty_segments(async_client, temp_images_dir, cleanup_projects):
    """GET /api/v1/projects/{uuid}/images/status with empty segments returns {}."""
    # Create a project
    create_resp = await async_client.post("/api/v1/projects", json={"name": "Image Test"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_uuid = project["uuid"]

    # Create segments.json with empty segments list
    project_dir = os.path.join(temp_images_dir, project_uuid)
    segments_path = os.path.join(project_dir, "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump({"segments": []}, f)

    response = await async_client.get(f"/api/v1/projects/{project_uuid}/images/status")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert response.json() == {}
