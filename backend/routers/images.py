import os
import json
import logging
from io import BytesIO
from fastapi import APIRouter, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from PIL import Image

images_router = APIRouter()

PROJECTS_BASE_DIR = os.path.join("..", "projects")

logger = logging.getLogger(__name__)

TARGET_RATIO = 16 / 9  # 1.777...
TOLERANCE = 0.01  # 1% tolerance
MIN_WIDTH = 1920
MIN_HEIGHT = 1080


def _get_project_dir(project_uuid: str) -> str:
    return os.path.join(PROJECTS_BASE_DIR, project_uuid)


def _get_segments_path(project_uuid: str) -> str:
    return os.path.join(_get_project_dir(project_uuid), "segments.json")


def _get_image_path(project_uuid: str, segment_index: int) -> str:
    project_dir = _get_project_dir(project_uuid)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    return os.path.join(images_dir, f"{segment_index:04d}.png")


def _load_segments(project_uuid: str) -> dict:
    segments_path = _get_segments_path(project_uuid)
    if not os.path.exists(segments_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project segments not found",
        )
    with open(segments_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_segments(project_uuid: str, data: dict) -> None:
    segments_path = _get_segments_path(project_uuid)
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@images_router.post("/projects/{project_uuid}/images/{segment_index}")
async def upload_image(project_uuid: str, segment_index: int, file: UploadFile = File(...)):
    """Upload a PNG image for a segment with validation and RGBA→RGB conversion."""
    # Validate MIME type
    if file.content_type != "image/png":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PNG only",
        )

    # Validate project exists
    project_dir = _get_project_dir(project_uuid)
    if not os.path.exists(project_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    # Open image with Pillow
    try:
        image = Image.open(BytesIO(content))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image file: {exc}",
        )

    # Validate format is PNG
    if image.format != "PNG":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PNG only",
        )

    # Validate aspect ratio (16:9 within 1% tolerance)
    width, height = image.size
    if height == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image dimensions",
        )

    actual_ratio = width / height
    lower_bound = TARGET_RATIO * (1 - TOLERANCE)
    upper_bound = TARGET_RATIO * (1 + TOLERANCE)

    if not (lower_bound <= actual_ratio <= upper_bound):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image must be 16:9 aspect ratio",
        )

    # Warn if resolution is below minimum
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        logger.warning(
            "Image resolution %dx%d is below minimum %dx%d for project %s segment %d",
            width, height, MIN_WIDTH, MIN_HEIGHT, project_uuid, segment_index,
        )

    # Convert RGBA → RGB if needed
    if image.mode == "RGBA":
        # Create white background and composite
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])  # Use alpha channel as mask
        image = background
    elif image.mode != "RGB":
        # Convert any other mode to RGB
        image = image.convert("RGB")

    # Save image
    image_path = _get_image_path(project_uuid, segment_index)
    image.save(image_path, "PNG")

    # Update segments.json
    segments_data = _load_segments(project_uuid)
    segments = segments_data.get("segments", [])

    # Find segment by index
    segment_found = False
    for segment in segments:
        if segment.get("segment_index") == segment_index:
            segment["image_path"] = image_path
            segment_found = True
            break

    if not segment_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {segment_index} not found",
        )

    _save_segments(project_uuid, segments_data)

    return {
        "segment_index": segment_index,
        "image_path": image_path,
    }


@images_router.get("/projects/{project_uuid}/images/{segment_index}")
async def get_image(project_uuid: str, segment_index: int):
    """Retrieve an uploaded image for a segment."""
    project_dir = _get_project_dir(project_uuid)
    if not os.path.exists(project_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    image_path = _get_image_path(project_uuid, segment_index)
    if not os.path.exists(image_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    return FileResponse(image_path, media_type="image/png")
