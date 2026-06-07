"""Tests for services.prompts — StyleProfile registry and message builders."""

import inspect
import json

import pytest

from services.prompts import (
    StyleProfile,
    STYLES,
    DEFAULT_STYLE_ID,
    get_style,
    SHOT_TYPES,
    build_character_extraction_messages,
    build_front_profile_messages,
    build_turnaround_messages,
    build_segment_breakdown_messages,
    build_segment_prompts_messages,
)


# ---------------------------------------------------------------------------
# Registry & helpers
# ---------------------------------------------------------------------------

def test_default_style_id():
    assert DEFAULT_STYLE_ID == "secret_level"


def test_get_style_known():
    assert get_style("secret_level") is STYLES["secret_level"]


def test_get_style_nonexistent_returns_default():
    assert get_style("nonexistent") is STYLES[DEFAULT_STYLE_ID]


def test_styles_has_exactly_one_entry():
    assert len(STYLES) == 1
    assert "secret_level" in STYLES


def test_shot_types_tuple():
    assert isinstance(SHOT_TYPES, tuple)
    expected = (
        "extreme wide",
        "wide",
        "medium",
        "close-up",
        "extreme close-up",
        "over-the-shoulder",
        "Dutch angle",
        "bird's eye",
        "worm's eye",
        "POV",
        "establishing shot",
        "aerial/drone",
    )
    assert SHOT_TYPES == expected


# ---------------------------------------------------------------------------
# Character extraction (style-invariant)
# ---------------------------------------------------------------------------

def test_character_extraction_messages_shape():
    messages = build_character_extraction_messages("Alice is brave.")
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_character_extraction_system_keywords():
    messages = build_character_extraction_messages("Alice is brave.")
    system = messages[0]["content"]
    assert "character extraction engine" in system
    assert "speaking" in system
    assert "creature" in system
    assert "npc_entity" in system
    assert "major" in system
    assert "minor" in system
    assert "Do NOT leave fields blank" in system


def test_character_extraction_user_xml_tag():
    messages = build_character_extraction_messages("Alice is brave.")
    user = messages[1]["content"]
    assert "<script>" in user
    assert "Alice is brave." in user
    assert "</script>" in user


def test_character_extraction_no_style_param():
    sig = inspect.signature(build_character_extraction_messages)
    assert "style" not in sig.parameters


# ---------------------------------------------------------------------------
# Front profile
# ---------------------------------------------------------------------------

def test_front_profile_messages_shape():
    style = STYLES["secret_level"]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_front_profile_messages(characters, style)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_front_profile_system_injects_style():
    style = STYLES["secret_level"]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_front_profile_messages(characters, style)
    system = messages[0]["content"]
    assert style.art_role_phrase in system
    assert style.front_profile_anchor in system
    assert style.prohibitions in system
    assert "Front Profile" in system
    assert "Important rules" in system


def test_front_profile_user_xml_tag():
    style = STYLES["secret_level"]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_front_profile_messages(characters, style)
    user = messages[1]["content"]
    assert "<characters>" in user
    assert "Alice" in user
    assert "</characters>" in user


def test_front_profile_accepts_string_characters():
    style = STYLES["secret_level"]
    characters_str = "Alice: brave knight"
    messages = build_front_profile_messages(characters_str, style)
    user = messages[1]["content"]
    assert characters_str in user


# ---------------------------------------------------------------------------
# Turnaround
# ---------------------------------------------------------------------------

def test_turnaround_messages_shape():
    style = STYLES["secret_level"]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_turnaround_messages(characters, style)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_turnaround_system_injects_style():
    style = STYLES["secret_level"]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_turnaround_messages(characters, style)
    system = messages[0]["content"]
    assert style.art_role_phrase in system
    assert style.turnaround_anchor in system
    assert style.prohibitions in system
    assert "Turnaround" in system
    assert "Important rules" in system


def test_turnaround_user_xml_tag():
    style = STYLES["secret_level"]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_turnaround_messages(characters, style)
    user = messages[1]["content"]
    assert "<characters>" in user
    assert "Alice" in user
    assert "</characters>" in user


# ---------------------------------------------------------------------------
# Segment breakdown (style-invariant)
# ---------------------------------------------------------------------------

def test_segment_breakdown_messages_shape():
    messages = build_segment_breakdown_messages("Script text.", '[{"word":"test"}]')
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_segment_breakdown_system_keywords():
    messages = build_segment_breakdown_messages("Script text.", '[{"word":"test"}]')
    system = messages[0]["content"]
    assert "video editor" in system
    assert "3–10 seconds" in system
    assert "≥1.5 seconds" in system
    assert "Return ONLY the JSON object" in system


def test_segment_breakdown_user_xml_tags():
    messages = build_segment_breakdown_messages("Script text.", '[{"word":"test"}]')
    user = messages[1]["content"]
    assert "<script>" in user
    assert "<word_timestamps>" in user
    assert "Script text." in user


def test_segment_breakdown_no_style_param():
    sig = inspect.signature(build_segment_breakdown_messages)
    assert "style" not in sig.parameters


# ---------------------------------------------------------------------------
# Segment prompts (Pass 2)
# ---------------------------------------------------------------------------

def test_segment_prompts_messages_shape():
    style = STYLES["secret_level"]
    segments = [{"segment_index": 1, "script_line": "Alice walks."}]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_segment_prompts_messages(segments, characters, style)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_segment_prompts_system_injects_style():
    style = STYLES["secret_level"]
    segments = [{"segment_index": 1, "script_line": "Alice walks."}]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_segment_prompts_messages(segments, characters, style)
    system = messages[0]["content"]
    assert style.segment_scene_anchor in system
    assert style.negative_style_example in system
    assert "no text, no watermark, no logo, no UI elements" in system


def test_segment_prompts_system_contains_shot_types():
    style = STYLES["secret_level"]
    segments = [{"segment_index": 1, "script_line": "Alice walks."}]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_segment_prompts_messages(segments, characters, style)
    system = messages[0]["content"]
    for shot in SHOT_TYPES:
        assert shot in system, f"SHOT_TYPE '{shot}' missing from system prompt"


def test_segment_prompts_system_contains_examples_and_rules():
    style = STYLES["secret_level"]
    segments = [{"segment_index": 1, "script_line": "Alice walks."}]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_segment_prompts_messages(segments, characters, style)
    system = messages[0]["content"]
    assert "Example Good Prompt" in system
    assert "Example Bad Prompt" in system
    assert "Do NOT copy the full character profile" in system
    assert "Do NOT paste the full profile prompt" in system


def test_segment_prompts_user_xml_tags():
    style = STYLES["secret_level"]
    segments = [{"segment_index": 1, "script_line": "Alice walks."}]
    characters = [{"name": "Alice", "description": "Brave knight."}]
    messages = build_segment_prompts_messages(segments, characters, style)
    user = messages[1]["content"]
    assert "<segments>" in user
    assert "<characters>" in user
    assert "Alice walks." in user


# ---------------------------------------------------------------------------
# Hypothetical second style — not hard-coded
# ---------------------------------------------------------------------------

def test_hypothetical_second_style_profile_uses_different_anchors():
    """A second style yields different anchors; builders are not hard-coded."""
    alt_style = StyleProfile(
        id="test_style",
        display_name="Test Style",
        art_role_phrase="You are a test artist.",
        front_profile_anchor="Test front anchor",
        turnaround_anchor="Test turnaround anchor",
        segment_scene_anchor="Test scene anchor",
        prohibitions="Never use test-ban language",
        negative_style_example="Test wrong style",
    )
    characters = [{"name": "Bob", "description": "Test character."}]
    segments = [{"segment_index": 1, "script_line": "Bob walks."}]

    front_msgs = build_front_profile_messages(characters, alt_style)
    assert "Test front anchor" in front_msgs[0]["content"]
    assert "Never use test-ban language" in front_msgs[0]["content"]
    assert "Secret Level" not in front_msgs[0]["content"]

    turn_msgs = build_turnaround_messages(characters, alt_style)
    assert "Test turnaround anchor" in turn_msgs[0]["content"]
    assert "Never use test-ban language" in turn_msgs[0]["content"]
    assert "Secret Level" not in turn_msgs[0]["content"]

    seg_msgs = build_segment_prompts_messages(segments, characters, alt_style)
    assert "Test scene anchor" in seg_msgs[0]["content"]
    assert "Test wrong style" in seg_msgs[0]["content"]


def test_builders_jsonify_non_string_inputs():
    """When dict/list inputs are passed, they are JSON-serialized in user tags."""
    style = STYLES["secret_level"]
    characters = [{"name": "Alice"}]
    segments = [{"segment_index": 1, "script_line": "Hi"}]

    front = build_front_profile_messages(characters, style)
    user = front[1]["content"]
    assert json.loads(user.split("<characters>")[1].split("</characters>")[0].strip()) == characters

    seg = build_segment_prompts_messages(segments, characters, style)
    user = seg[1]["content"]
    seg_json = user.split("<segments>")[1].split("</segments>")[0].strip()
    char_json = user.split("<characters>")[1].split("</characters>")[0].strip()
    assert json.loads(seg_json) == segments
    assert json.loads(char_json) == characters


def test_anime_only_in_profile_values():
    """The literal 'anime' (case-sensitive) appears only inside the secret_level profile values."""
    import services.prompts as prompts_module
    import pathlib

    source_path = pathlib.Path(inspect.getfile(prompts_module))
    lines = source_path.read_text(encoding="utf-8").splitlines()

    # Find the STYLES block boundaries
    styles_start = None
    styles_end = None
    for i, line in enumerate(lines, start=1):
        if "STYLES: dict[str, StyleProfile] = {" in line:
            styles_start = i
        if styles_start is not None and line.strip() == "}":
            styles_end = i
            break

    assert styles_start is not None
    assert styles_end is not None

    for i, line in enumerate(lines, start=1):
        if "anime" in line:
            # Must be inside the STYLES block (prohibitions value)
            assert styles_start <= i <= styles_end, (
                f"Lowercase 'anime' found outside profile values at line {i}: {line.strip()!r}"
            )
