"""Test backend server with mocked AI services for E2E testing.

Run with: python run_test_backend.py
"""
import os
import sys
import json
import tempfile
import shutil
import asyncio

# Set up test environment BEFORE importing backend modules
os.environ.setdefault("OPENAI_API_KEY", "test-key")

test_db_path = os.path.join(tempfile.gettempdir(), "test_e2e_backend.db")
test_projects_dir = tempfile.mkdtemp(prefix="test_e2e_projects_")

# Patch database path
import models.database
models.database.DB_PATH = test_db_path

# ── Mock AI services BEFORE importing routers ───────────────────────────────
import services.whisper as whisper_module
import services.fireworks as fireworks_module
import services.ffmpeg as ffmpeg_module

async def mock_transcribe_audio(file_path: str) -> dict:
    """Return mock word-level transcription."""
    return {
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
            {"word": "This", "start": 1.1, "end": 1.5},
            {"word": "is", "start": 1.6, "end": 1.8},
            {"word": "a", "start": 1.9, "end": 2.0},
            {"word": "test", "start": 2.1, "end": 2.5},
        ]
    }

whisper_module.transcribe_audio = mock_transcribe_audio


class MockFireworksClient:
    """Mock Fireworks client that returns canned responses."""

    def __init__(self, *args, **kwargs):
        pass

    async def chat_completion(self, messages, **kwargs):
        content = " ".join(m.get("content", "") for m in messages)
        content_lower = content.lower()

        # Character extraction
        if "extract all characters" in content_lower:
            return {
                "characters": [
                    {
                        "name": "Alice",
                        "type": "protagonist",
                        "importance": "main",
                        "description": "A curious explorer.",
                    }
                ]
            }

        # Character prompts
        if "front_profile_prompt" in content_lower or "turnaround" in content_lower:
            return {
                "characters": [
                    {
                        "name": "Alice",
                        "front_profile_prompt": "Front profile of Alice, a curious explorer.",
                        "turnaround_prompt": "Turnaround reference of Alice.",
                    }
                ]
            }

        # Segment breakdown
        if "break the script into logical segments" in content_lower:
            return {
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

        # Segment prompts
        if "image generation prompt" in content_lower:
            return {
                "segments": [
                    {
                        "segment_index": 0,
                        "script_line": "Hello world.",
                        "segment_prompt": "A welcoming scene with Alice.",
                        "characters_present": ["Alice"],
                        "start_time": 0.0,
                        "end_time": 1.0,
                        "duration": 1.0,
                    },
                    {
                        "segment_index": 1,
                        "script_line": "This is a test.",
                        "segment_prompt": "Alice taking a test.",
                        "characters_present": ["Alice"],
                        "start_time": 1.1,
                        "end_time": 2.5,
                        "duration": 1.4,
                    },
                ]
            }

        return {}


fireworks_module.FireworksClient = MockFireworksClient


async def mock_generate_video(project_dir, segments, voiceover_path, should_burn_captions=False):
    """Create fake output.mp4 and captions.srt without running FFmpeg."""
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "output.mp4")
    with open(output_path, "wb") as f:
        f.write(b"fake_mp4_content")

    # Create captions.srt
    srt_path = os.path.join(project_dir, "captions.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:01,000\nHello world.\n")

    # Write progress
    ffmpeg_module._write_progress(project_dir, 100)
    return output_path


ffmpeg_module.generate_video = mock_generate_video


# Patch projects base dir in all modules
import routers.projects as projects_module
import services.state as state_module
import routers.segments as segments_module
import routers.video as video_module
import routers.images as images_module
import routers.characters as characters_module
import services.srt as srt_module

projects_module.PROJECTS_BASE_DIR = test_projects_dir
state_module.PROJECTS_BASE_DIR = test_projects_dir
segments_module.PROJECTS_BASE_DIR = test_projects_dir
video_module.PROJECTS_BASE_DIR = test_projects_dir
images_module.PROJECTS_BASE_DIR = test_projects_dir
characters_module.PROJECTS_BASE_DIR = test_projects_dir
srt_module.PROJECTS_BASE_DIR = test_projects_dir

# Import app
from main import app

# Initialize database
async def init_db():
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    await models.database.init_db()

asyncio.run(init_db())


# ── Cleanup helpers ─────────────────────────────────────────────────────────
def cleanup():
    """Remove temp database and projects directory."""
    shutil.rmtree(test_projects_dir, ignore_errors=True)
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


if __name__ == "__main__":
    import uvicorn
    import atexit

    # Only auto-cleanup if explicitly requested
    if os.environ.get("TEST_BACKEND_CLEANUP", "1") == "1":
        atexit.register(cleanup)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
