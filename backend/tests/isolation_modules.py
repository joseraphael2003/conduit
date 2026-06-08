"""Centralized test isolation: modules whose PROJECTS_BASE_DIR must be patched."""
import routers.projects as projects_module
import services.state as state_module
import routers.segments as segments_module
import services.srt as srt_module
import routers.images as images_module
import routers.video as video_module
import services.ffmpeg as ffmpeg_module

PATCHED_MODULES = (
    projects_module,
    state_module,
    segments_module,
    srt_module,
    images_module,
    video_module,
    ffmpeg_module,
)
