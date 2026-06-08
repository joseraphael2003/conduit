import os
import json
import uuid
import logging
from io import BytesIO
from fastapi import APIRouter, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from PIL import Image
from config import PROJECTS_BASE_DIR

images_router = APIRouter()

logger = logging.getLogger(__name__)

TARGET_RATIO = 16 / 9  # 1.777...
TOLERANCE = 0.01  # 1% tolerance
MIN_WIDTH = 1920
MIN_HEIGHT = 1080


def _get_project_dir(project_uuid: str) -> str:
    return os.path.join(PROJECTS_BASE_DIR, project_uuid)


def _get_segments_path(project_uuid: str) -> str:
    project_dir = _get_project_dir(project_uuid)
    # Check .conduit/ first, then fallback to project root for backward compatibility
    conduit_path = os.path.join(project_dir, ".conduit", "segments.json")
    if os.path.exists(conduit_path):
        return conduit_path
    return os.path.join(project_dir, "segments.json")


def _get_image_path(project_uuid: str, segment_index: int) -> str:
    project_dir = _get_project_dir(project_uuid)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    return os.path.join(images_dir, f"{segment_index:04d}.png")


def _get_image_path_by_id(project_uuid: str, segment_id: str) -> str:
    project_dir = _get_project_dir(project_uuid)
    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    return os.path.join(images_dir, f"{segment_id}.png")


def _resolve_image_path(project_uuid: str, segments: list, segment_index: int) -> str:
    for segment in segments:
        if segment.get("segment_index") == segment_index:
            if segment.get("segment_id"):
                return _get_image_path_by_id(project_uuid, segment["segment_id"])
            break
    return _get_image_path(project_uuid, segment_index)


def _ensure_segment_ids_and_migrate(project_uuid: str) -> None:
    segments_data = _load_segments(project_uuid)
    segments = segments_data.get("segments", [])
    changed = False
    for segment in segments:
        if not segment.get("segment_id"):
            segment["segment_id"] = str(uuid.uuid4())
            changed = True
            # Rename legacy file if it exists
            legacy_path = _get_image_path(project_uuid, segment["segment_index"])
            if os.path.exists(legacy_path):
                new_path = _get_image_path_by_id(project_uuid, segment["segment_id"])
                os.rename(legacy_path, new_path)
                segment["image_path"] = new_path
    if changed:
        _save_segments(project_uuid, segments_data)


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

    _ensure_segment_ids_and_migrate(project_uuid)

    # Load segments and find target segment
    segments_data = _load_segments(project_uuid)
    segments = segments_data.get("segments", [])

    target_segment = None
    for segment in segments:
        if segment.get("segment_index") == segment_index:
            target_segment = segment
            break

    if not target_segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {segment_index} not found",
        )

    # Ensure segment_id
    if not target_segment.get("segment_id"):
        target_segment["segment_id"] = str(uuid.uuid4())
        _save_segments(project_uuid, segments_data)

    segment_id = target_segment["segment_id"]

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
        logging.error("Image validation failed", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file — please upload a valid PNG",
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
    image_path = _get_image_path_by_id(project_uuid, segment_id)
    image.save(image_path, "PNG")

    # Update segment
    target_segment["image_path"] = image_path
    _save_segments(project_uuid, segments_data)

    return {
        "segment_index": segment_index,
        "image_path": image_path,
    }


@images_router.get("/projects/{project_uuid}/images/status")
async def get_images_status(project_uuid: str):
    """Return a map of segment_index -> bool for every segment in segments.json."""
    project_dir = _get_project_dir(project_uuid)
    if not os.path.exists(project_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    _ensure_segment_ids_and_migrate(project_uuid)

    segments_data = _load_segments(project_uuid)
    segments = segments_data.get("segments", [])

    if not segments:
        return {}

    status_map = {}
    for segment in segments:
        segment_index = segment.get("segment_index")
        if segment_index is not None:
            segment_id = segment.get("segment_id")
            image_path = _get_image_path_by_id(project_uuid, segment_id)
            status_map[str(segment_index)] = os.path.exists(image_path)

    return status_map


@images_router.get("/projects/{project_uuid}/images/{segment_index}")
async def get_image(project_uuid: str, segment_index: int):
    """Retrieve an uploaded image for a segment."""
    project_dir = _get_project_dir(project_uuid)
    if not os.path.exists(project_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    segments_data = _load_segments(project_uuid)
    segments = segments_data.get("segments", [])
    image_path = _resolve_image_path(project_uuid, segments, segment_index)

    if not os.path.exists(image_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    return FileResponse(image_path, media_type="image/png")
