import os
import json
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.ffmpeg import generate_video
from services.state import update_state
from models.state import ProjectState

video_router = APIRouter()

PROJECTS_BASE_DIR = os.path.join("..", "projects")


def _get_project_dir(project_uuid: str) -> str:
    return os.path.join(PROJECTS_BASE_DIR, project_uuid)


class VideoGenerateRequest(BaseModel):
    burn_captions: bool = False


def _write_video_error(uuid: str, message: str) -> None:
    """Write video error to the project's state.json."""
    state_json_path = os.path.join(_get_project_dir(uuid), ".conduit", "state.json")
    if os.path.exists(state_json_path):
        try:
            with open(state_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
        data["video_error"] = message
        data["updated_at"] = datetime.utcnow().isoformat()
        try:
            with open(state_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass


def _clear_video_error(uuid: str) -> None:
    """Clear video error from the project's state.json."""
    state_json_path = os.path.join(_get_project_dir(uuid), ".conduit", "state.json")
    if os.path.exists(state_json_path):
        try:
            with open(state_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
        data.pop("video_error", None)
        data["updated_at"] = datetime.utcnow().isoformat()
        try:
            with open(state_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass


@video_router.get("/projects/{project_uuid}/video/srt")
async def get_srt(project_uuid: str):
    """Download the captions.srt file for a project."""
    project_dir = _get_project_dir(project_uuid)
    if not os.path.exists(project_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    srt_path = os.path.join(project_dir, "captions.srt")
    if not os.path.exists(srt_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SRT file not found",
        )

    return FileResponse(
        srt_path,
        media_type="application/octet-stream",
        filename="captions.srt",
    )


@video_router.get("/projects/{project_uuid}/video/ass")
async def get_ass(project_uuid: str):
    """Download the captions.ass file for a project."""
    project_dir = _get_project_dir(project_uuid)
    if not os.path.exists(project_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    ass_path = os.path.join(project_dir, "captions.ass")
    if not os.path.exists(ass_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ASS file not found",
        )

    return FileResponse(
        ass_path,
        media_type="application/octet-stream",
        filename="captions.ass",
    )


@video_router.post("/projects/{uuid}/video/generate")
async def generate_video_endpoint(uuid: str, request: VideoGenerateRequest):
    """Generate video from segments and voiceover."""
    project_dir = _get_project_dir(uuid)

    if not os.path.exists(project_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Read segments.json (check both .conduit/ and project root for backward compatibility)
    segments_path = os.path.join(project_dir, ".conduit", "segments.json")
    if not os.path.exists(segments_path):
        # Fallback to project root for backward compatibility
        segments_path = os.path.join(project_dir, "segments.json")
        if not os.path.exists(segments_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="segments.json not found",
            )

    with open(segments_path, "r", encoding="utf-8") as f:
        segments_data = json.load(f)

    segments = segments_data.get("segments", [])
    if not segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No segments found",
        )

    # Validate all segments have image_path
    missing_images = [
        i
        for i, seg in enumerate(segments)
        if not seg.get("image_path") or not os.path.exists(seg["image_path"])
    ]
    if missing_images:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{len(missing_images)} segments missing images",
        )

    # Read voiceover.mp3
    voiceover_path = os.path.join(project_dir, "voiceover.mp3")
    if not os.path.exists(voiceover_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="voiceover.mp3 not found",
        )

    # Calculate total duration
    total_duration = sum(seg.get("duration", 0) for seg in segments)

    # Clear any previous error before starting
    _clear_video_error(uuid)

    try:
        output_path = await generate_video(
            project_dir,
            segments,
            voiceover_path,
            request.burn_captions,
        )
    except HTTPException as exc:
        if exc.status_code == 500 and "FFmpeg failed" in str(exc.detail):
            _write_video_error(uuid, str(exc.detail))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=exc.detail,
            )
        raise

    # Update state to step_5_complete
    await update_state(uuid, ProjectState.STEP_5_COMPLETE)

    return {
        "output_path": "output/output.mp4",
        "duration": round(total_duration, 1),
    }


@video_router.get("/projects/{uuid}/video/status")
async def get_video_status(uuid: str):
    """Get video generation status."""
    project_dir = _get_project_dir(uuid)
    state_json_path = os.path.join(project_dir, ".conduit", "state.json")

    # Read segments.json for total_segments
    segments_path = os.path.join(project_dir, "segments.json")
    total_segments = 0
    if os.path.exists(segments_path):
        with open(segments_path, "r", encoding="utf-8") as f:
            segments_data = json.load(f)
        total_segments = len(segments_data.get("segments", []))

    status_info = {
        "status": "idle",
        "current_segment": 0,
        "total_segments": total_segments,
        "message": "",
    }

    if not os.path.exists(state_json_path):
        return status_info

    with open(state_json_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)

    video_error = state_data.get("video_error")
    video_progress = state_data.get("video_progress")

    if video_error:
        status_info["status"] = "error"
        status_info["message"] = video_error
    elif video_progress == 100:
        status_info["status"] = "completed"
        status_info["current_segment"] = total_segments
    elif video_progress is not None and video_progress > 0:
        status_info["status"] = "processing"
        if total_segments > 0:
            status_info["current_segment"] = int(video_progress / 100 * total_segments)
    else:
        status_info["status"] = "idle"

    return status_info


@video_router.get("/projects/{uuid}/video/logs")
async def get_video_logs(uuid: str, limit: int = 100):
    """Get the last N lines of ffmpeg stderr logs."""
    project_dir = _get_project_dir(uuid)
    log_path = os.path.join(project_dir, ".conduit", "ffmpeg.log")

    if not os.path.exists(log_path):
        return {"lines": []}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines = [line.rstrip("\n") for line in lines]
        return {"lines": lines[-limit:]}
    except OSError:
        return {"lines": []}


@video_router.get("/projects/{uuid}/video/download")
async def download_video(uuid: str):
    """Download the generated video."""
    project_dir = _get_project_dir(uuid)
    output_path = os.path.join(project_dir, "output", "output.mp4")

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename="output.mp4",
    )
