"""FFmpeg video generation service for the Conduit project."""

import asyncio
import datetime
import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List

from fastapi import HTTPException

FFMPEG_PATH = r"D:\Program Files\PROTEUS\INSTALL\Tools\Python\ffmpeg.exe"
PROJECTS_BASE_DIR = os.path.join("..", "projects")


def _run_ffmpeg(cmd: List[str], log_file: str | None = None) -> None:
    """Run an ffmpeg command and capture stderr to a log file if provided."""
    try:
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for line in process.stderr:
                    log.write(line)
                    log.flush()
                process.wait()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(
                        process.returncode, cmd, stderr="see log file"
                    )
        else:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg failed: {e.stderr}",
        )


def _write_progress(project_dir: str, progress: int) -> None:
    """Write video generation progress to the project's state.json."""
    state_json_path = os.path.join(project_dir, ".conduit", "state.json")
    if os.path.exists(state_json_path):
        try:
            with open(state_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
        data["video_progress"] = progress
        data["updated_at"] = datetime.datetime.utcnow().isoformat()
        try:
            with open(state_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass


def generate_segment_clip(
    image_path: str,
    duration: float,
    effect: str,
    output_path: str,
    log_file: str | None = None,
) -> None:
    """Generate a single segment MP4 from an image with an optional effect.

    Supported effects:
      - none:    loop image for duration
      - zoom_in: zoompan from 1.0 to 1.03
      - zoom_out: zoompan from 1.03 to 1.0
      - pan_left:  pan left (negative pan_speed)
      - pan_right: pan right (positive pan_speed)
      - pan_up:    pan up (positive pan_speed)
      - pan_down:  pan down (negative pan_speed)
    """
    total_frames = int(duration * 24)
    scale_pad = (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
    )
    common_args = [
        "-c:v", "libx264",
        "-r", "24",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        "-preset", "fast",
    ]

    if effect == "none":
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(duration),
            "-vf", scale_pad,
            *common_args,
            output_path,
        ]
    elif effect == "zoom_in":
        zoom_expr = f"1+on/{total_frames}*0.03"
        vf = f"zoompan=z='{zoom_expr}':d={total_frames}:fps=24,{scale_pad}"
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(duration),
            "-vf", vf,
            *common_args,
            output_path,
        ]
    elif effect == "zoom_out":
        zoom_expr = f"1.03-on/{total_frames}*0.03"
        vf = f"zoompan=z='{zoom_expr}':d={total_frames}:fps=24,{scale_pad}"
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(duration),
            "-vf", vf,
            *common_args,
            output_path,
        ]
    elif effect == "pan_left":
        pan_speed = -0.5
        x_expr = f"iw/2-(iw/zoom/2)+on*{pan_speed}"
        vf = f"zoompan=x='{x_expr}':d={total_frames}:fps=24,{scale_pad}"
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(duration),
            "-vf", vf,
            *common_args,
            output_path,
        ]
    elif effect == "pan_right":
        pan_speed = 0.5
        x_expr = f"iw/2-(iw/zoom/2)+on*{pan_speed}"
        vf = f"zoompan=x='{x_expr}':d={total_frames}:fps=24,{scale_pad}"
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(duration),
            "-vf", vf,
            *common_args,
            output_path,
        ]
    elif effect == "pan_up":
        pan_speed = 0.5
        y_expr = f"ih/2-(ih/zoom/2)+on*{pan_speed}"
        vf = f"zoompan=y='{y_expr}':d={total_frames}:fps=24,{scale_pad}"
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(duration),
            "-vf", vf,
            *common_args,
            output_path,
        ]
    elif effect == "pan_down":
        pan_speed = -0.5
        y_expr = f"ih/2-(ih/zoom/2)+on*{pan_speed}"
        vf = f"zoompan=y='{y_expr}':d={total_frames}:fps=24,{scale_pad}"
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(duration),
            "-vf", vf,
            *common_args,
            output_path,
        ]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown effect: {effect}",
        )

    _run_ffmpeg(cmd, log_file)


def concat_segments(
    segment_clips: List[str],
    concat_path: str,
    log_file: str | None = None,
) -> str:
    """Create an ffconcat file and run ffmpeg concat demuxer.

    Returns the path to the concatenated output video.
    """
    with open(concat_path, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for clip in segment_clips:
            # ffmpeg concat prefers forward slashes on all platforms
            f.write(f"file '{clip.replace(os.sep, '/')}'\n")

    output_path = concat_path.replace(".txt", ".mp4")
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_path,
        "-c", "copy",
        output_path,
    ]
    _run_ffmpeg(cmd, log_file)
    return output_path


def mix_audio(
    video_path: str,
    voiceover_path: str,
    output_path: str,
    log_file: str | None = None,
) -> None:
    """Mix voiceover audio into a video."""
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", video_path,
        "-i", voiceover_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]
    _run_ffmpeg(cmd, log_file)


def burn_captions(
    video_path: str,
    srt_path: str,
    output_path: str,
    log_file: str | None = None,
) -> None:
    """Burn SRT captions into a video using the ffmpeg subtitles filter."""
    srt_path_ffmpeg = srt_path.replace(os.sep, "/")
    vf = f"subtitles='{srt_path_ffmpeg}'"
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path,
    ]
    _run_ffmpeg(cmd, log_file)


# Keep a reference to avoid shadowing by the generate_video parameter.
_burn_captions_impl = burn_captions


async def generate_video(
    project_dir: str,
    segments: List[Dict[str, Any]],
    voiceover_path: str,
    burn_captions: bool = False,
) -> str:
    """Orchestrate the full video generation pipeline.

    Steps:
      1. Create a temp directory for segment clips.
      2. Generate each segment clip with progress tracking.
      3. Concatenate all segment clips.
      4. Mix in the voiceover audio.
      5. Optionally burn SRT captions.
      6. Copy the final result to project_dir/output/output.mp4.
      7. Clean up temp files.

    Returns the path to the final output video.
    """
    log_file = os.path.join(project_dir, ".conduit", "ffmpeg.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("")

    temp_dir = tempfile.mkdtemp()
    try:
        segment_clips: List[str] = []
        total_segments = len(segments)

        for i, segment in enumerate(segments):
            image_path = segment["image_path"]
            duration = segment["duration"]
            effect = segment.get("effect", "none")

            segment_path = os.path.join(temp_dir, f"segment_{i:04d}.mp4")
            await asyncio.to_thread(
                generate_segment_clip,
                image_path,
                duration,
                effect,
                segment_path,
                log_file,
            )
            segment_clips.append(segment_path)

            # Update progress after each segment
            progress = int((i + 1) / total_segments * 100)
            await asyncio.to_thread(_write_progress, project_dir, progress)

        # Concatenate segments
        concat_list_path = os.path.join(temp_dir, "concat.txt")
        concat_output = await asyncio.to_thread(
            concat_segments,
            segment_clips,
            concat_list_path,
            log_file,
        )

        # Mix voiceover audio
        mixed_path = os.path.join(temp_dir, "mixed.mp4")
        await asyncio.to_thread(
            mix_audio,
            concat_output,
            voiceover_path,
            mixed_path,
            log_file,
        )

        final_path = mixed_path
        if burn_captions:
            srt_path = os.path.join(project_dir, "captions.srt")
            if os.path.exists(srt_path):
                captioned_path = os.path.join(temp_dir, "captioned.mp4")
                await asyncio.to_thread(
                    _burn_captions_impl,
                    mixed_path,
                    srt_path,
                    captioned_path,
                    log_file,
                )
                final_path = captioned_path

        # Copy final result to output directory
        output_dir = os.path.join(project_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        final_output = os.path.join(output_dir, "output.mp4")
        shutil.copy(final_path, final_output)

        # Write completion progress
        await asyncio.to_thread(_write_progress, project_dir, 100)

        return final_output
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
