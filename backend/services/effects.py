"""Video effects service for zoompan filter generation."""

import random
from typing import List, Optional, Tuple


EFFECTS = {
    "none": None,
    "zoom_in": {"zoom_start": 1.0, "zoom_end": 1.03, "pan_speed": 0},
    "zoom_out": {"zoom_start": 1.03, "zoom_end": 1.0, "pan_speed": 0},
    "pan_left": {"zoom_start": 1.02, "zoom_end": 1.02, "pan_speed": -2},
    "pan_right": {"zoom_start": 1.02, "zoom_end": 1.02, "pan_speed": 2},
    "pan_up": {"zoom_start": 1.02, "zoom_end": 1.02, "pan_speed": 2},
    "pan_down": {"zoom_start": 1.02, "zoom_end": 1.02, "pan_speed": -2},
}


def get_effect_params(effect_name: str) -> Optional[dict]:
    """Return effect parameters for the given effect name.

    Args:
        effect_name: Name of the effect (e.g., "zoom_in", "pan_left").

    Returns:
        Dict of parameters or None for "none".

    Raises:
        KeyError: If the effect name is not recognized.
    """
    return EFFECTS[effect_name]


def build_zoompan_filter(effect_name: str, duration: float, fps: int = 24) -> str:
    """Build an ffmpeg zoompan filter string for the given effect.

    Args:
        effect_name: Name of the effect to apply.
        duration: Duration of the clip in seconds.
        fps: Frames per second. Defaults to 24.

    Returns:
        ffmpeg zoompan filter string.

    Raises:
        KeyError: If the effect name is not recognized.
        ValueError: If effect_name is "none" (no filter needed).
    """
    if effect_name == "none":
        raise ValueError('Cannot build zoompan filter for "none" effect')

    params = EFFECTS[effect_name]
    total_frames = int(duration * fps)
    zoom_start = params["zoom_start"]
    zoom_end = params["zoom_end"]
    pan_speed = params["pan_speed"]

    zoom_delta = zoom_end - zoom_start
    base = f"zoompan=d={total_frames}:s=1920x1080:fps={fps}"

    if effect_name in ("zoom_in", "zoom_out"):
        z_expr = f"{zoom_start}+on/{total_frames}*{zoom_delta}"
        return f"{base}:z='{z_expr}'"

    if effect_name in ("pan_left", "pan_right"):
        x_expr = f"iw/2-(iw/zoom/2)+on*{pan_speed}"
        return f"{base}:x='{x_expr}'"

    if effect_name in ("pan_up", "pan_down"):
        y_expr = f"ih/2-(ih/zoom/2)+on*{pan_speed}"
        return f"{base}:y='{y_expr}'"

    return base


def random_assign_effects(segments: list) -> List[Tuple[int, str]]:
    """Randomly assign an effect to each segment.

    No two adjacent segments are guaranteed to have the same effect.
    Uses a simple random pick for each segment.

    Args:
        segments: List of segment objects.

    Returns:
        List of (segment_index, effect_name) tuples.
    """
    non_none_effects = [name for name in EFFECTS if name != "none"]
    assignments: List[Tuple[int, str]] = []

    for i, _ in enumerate(segments):
        effect_name = random.choice(non_none_effects)
        assignments.append((i, effect_name))

    return assignments


def validate_effect(effect_name: str) -> bool:
    """Check if the effect name is valid.

    Args:
        effect_name: Name to validate.

    Returns:
        True if the effect exists, False otherwise.
    """
    return effect_name in EFFECTS
