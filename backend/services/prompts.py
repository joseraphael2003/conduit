"""Prompt builders and style registry for Fireworks AI LLM calls.

All builders return list[dict] in the shape expected by services.fireworks:
  [{"role": "system", "content": ...}, {"role": "user", "content": ...}]

Style-inverting rules (prohibitions + negative_style_example fields)
come from the StyleProfile, never from builder scaffolding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Style registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StyleProfile:
    id: str
    display_name: str
    art_role_phrase: str
    front_profile_anchor: str
    turnaround_anchor: str
    segment_scene_anchor: str
    prohibitions: str
    negative_style_example: str


STYLES: dict[str, StyleProfile] = {
    "secret_level": StyleProfile(
        id="secret_level",
        display_name="Secret Level / Love Death and Robots",
        art_role_phrase="You are a character art prompt writer for an animated series in the visual style of Secret Level and Love Death and Robots.",
        front_profile_anchor="Secret Level / Love Death and Robots style animation, photorealistic 3D render, cinematic lighting, subsurface skin scattering, physically based rendering, hyper-detailed face, face depth, realistic eyes, volumetric lighting, sharp detailed textures, clean render",
        turnaround_anchor="Secret Level / Love Death and Robots style animation, photorealistic 3D render, character turnaround reference sheet, professional character modeling sheet, cinematic lighting, subsurface skin scattering, physically based rendering, hyper-detailed face, face depth, realistic eyes, sharp detailed textures, clean render, pure white background, landscape composition, no text, no watermark, no logo",
        segment_scene_anchor="Cinematic wide shot, photorealistic 3D render, Secret Level / Love Death and Robots style, highly detailed, cinematic lighting, volumetric fog",
        prohibitions="Never use anime or cel-shading language",
        negative_style_example="Anime style, cel-shaded, chibi character, Alice in a forest, kawaii, sparkles, bright pastel colors.",
    )
}

DEFAULT_STYLE_ID = "secret_level"


def get_style(style_id: str) -> StyleProfile:
    """Return the StyleProfile for *style_id*, falling back to the default."""
    return STYLES.get(style_id, STYLES[DEFAULT_STYLE_ID])


# ---------------------------------------------------------------------------
# Shot vocabulary
# ---------------------------------------------------------------------------

SHOT_TYPES: tuple[str, ...] = (
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_json_str(value: object) -> str:
    """Coerce *value* to a JSON string if it is not already a string."""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_character_extraction_messages(script: str) -> list[dict]:
    """§4.1 — Character extraction (style-invariant)."""
    system = (
        "You are a character extraction engine. Read the script and identify all entities that are visually important in the story.\n\n"
        "Extract:\n"
        "1. Named speaking characters (e.g., \"Alice\", \"Bob\")\n"
        "2. Significant NPCs or creatures that appear visually (e.g., \"the dragon\", \"the old merchant\")\n"
        "3. Any NPC entity that has a visual presence\n\n"
        "For each entity, output:\n"
        "- name: the canonical name\n"
        '- type: "speaking" | "creature" | "npc_entity"\n'
        '- importance: "major" if the entity appears in multiple scenes or is central to the plot. '
        '"minor" if they appear once or are background.\n'
        "- description: a detailed visual description of the character's appearance, clothing, and expression. "
        "If the script does not describe them in detail, infer a visually interesting design that fits the narrative. "
        "Do NOT leave fields blank.\n\n"
        'Return ONLY a JSON object with a top-level "characters" array. Each element of "characters" is an object with fields: name, type, importance, description.'
    )
    user = f"<script>\n{script}\n</script>"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_character_timeline_messages(
    script: str, characters: object, style: StyleProfile | None = None
) -> list[dict]:
    """§4.1b — Character timeline / version extraction (style-invariant).

    Identifies distinct visual versions of each character across narrative time.
    """
    system = (
        "You are a character timeline engine. Read the full script and, for each provided person, identify distinct visual "
        "versions across narrative time. A version is a significant transformation in age, body, or role, not a costume change.\n\n"
        "For each person, output one version entry per distinct life-stage.\n\n"
        "Output fields per version:\n"
        "- name: unique version name (e.g., \"Hero (young)\", \"Hero (old)\")\n"
        "- base_name: the canonical character name shared across all versions\n"
        "- version_label: short label for this life-stage (e.g., \"young\", \"old\", \"default\")\n"
        "- version_index: integer index for this version (0, 1, 2...)\n"
        "- appears_from: the grounded narrative boundary where this version first appears. Use explicit script evidence. "
        "Do NOT invent facts. If only one version exists, use empty string.\n"
        '- type: "speaking" | "creature" | "npc_entity"\n'
        '- importance: "major" if the entity appears in multiple scenes or is central to the plot. '
        '"minor" if they appear once or are background.\n'
        "- description: detailed visual description of this version's appearance, clothing, and expression at this life-stage.\n"
        "- identity_anchor: stable facial / anatomical traits that MUST stay consistent across all versions of this base_name. "
        "Duplicate the same identity_anchor onto every version of the same base_name.\n\n"
        "Rules:\n"
        "- Single-appearance characters get exactly one version: version_label=\"default\", version_index=0, appears_from=\"\".\n"
        "- Do NOT create versions for costume changes or minor outfit variations.\n"
        "- Ground every version boundary in explicit script evidence.\n"
        "- Do NOT leave fields blank.\n\n"
        "Output shape: CharacterList (a JSON object with a \"characters\" array)."
    )
    user = (
        f"<script>\n{script}\n</script>\n\n"
        f"<characters>\n{_to_json_str(characters)}\n</characters>"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_front_profile_messages(characters: object, style: StyleProfile) -> list[dict]:
    """§4.2 Prompt A — Front profile prompt generation."""
    system = (
        f"{style.art_role_phrase}\n\n"
        "For each character in the list, generate a front profile prompt.\n\n"
        "Prompt — Front Profile:\n"
        "Style anchors (always include):\n"
        f"{style.front_profile_anchor}\n"
        "Then append in this order:\n"
        "Age, gender, race or species type\n"
        "Hair description (length, style, color, texture)\n"
        "Skin tone and build\n"
        "Eye description (color, shape, expression)\n"
        "Face shape and expression\n"
        "Outfit or upper body description\n"
        "Lower body or full body description if non-humanoid\n"
        "Shot type and framing\n"
        "Background\n"
        "no text, no watermark, no logo\n"
        "Rules:\n"
        "Keep prompts to 2-4 lines maximum, comma-separated, no full sentences\n"
        f"{style.prohibitions}\n"
        "For hybrid or monster characters, describe the non-human parts with precise anatomical and material detail\n"
        "Always end with background description and no text\n\n"
        "Important rules:\n"
        "- For minor characters with minimal description, keep the prompt shorter but still fully specified.\n"
        "- For major characters, provide more detailed prompts.\n"
        "- Do NOT leave fields blank.\n\n"
        "Version consistency rules:\n"
        "- Each character entry may include an identity_anchor, version_label, and appears_from.\n"
        "- If identity_anchor is present, it describes stable facial / anatomical traits that MUST stay consistent "
        "across every version of this character. Preserve these traits in the generated prompt.\n"
        "- If version_label and appears_from are present, the prompt must reflect this specific life-stage only.\n"
        "- Do NOT mix traits from different versions into the same prompt.\n\n"
        'Return ONLY a JSON object with a top-level "characters" array; each element has fields: name, front_profile_prompt.'
    )
    user = f"<characters>\n{_to_json_str(characters)}\n</characters>"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_turnaround_messages(characters: object, style: StyleProfile) -> list[dict]:
    """§4.2 Prompt B — Turnaround reference sheet prompt generation."""
    system = (
        f"{style.art_role_phrase}\n\n"
        "For each character in the list, generate a turnaround reference sheet prompt.\n\n"
        "Prompt — Turnaround Reference Sheet:\n"
        "Always open with:\n"
        f"{style.turnaround_anchor}\n"
        "Then append in this order:\n"
        "Age, gender, race or species type\n"
        "Hair description (length, style, color, texture)\n"
        "Skin tone and build\n"
        "Eye description (color, shape, expression)\n"
        "Face shape and expression\n"
        "Outfit or upper body description\n"
        "Lower body or full body if non-humanoid\n"
        "Three-view turnaround instruction: left side of composition shows three full-body views — front, left-side profile, and back — "
        "same character, identical proportions, natural standing pose, arms at sides, eye-level camera\n"
        "Upper-right instruction: upper-right section shows six head-angle references — front-facing, slight downward, back of head, "
        "left-side profile, near-side comparison, 3/4 profile\n"
        "Lower-right instruction: lower-right section shows six close-up detail shots — upper garment texture, lower body clothing, "
        "hip detail, leg or skin texture, eyes and facial features, full shoe close-up\n"
        "strict character consistency throughout, no cropping, no extra props, no text, no logo, no watermark\n"
        "Rules:\n"
        "Keep the character description portion to 2-4 lines, comma-separated, no full sentences\n"
        f"{style.prohibitions}\n"
        "For non-humanoid or hybrid characters, replace shoe/clothing detail shots with anatomically appropriate equivalents\n"
        "All three turnaround views and all detail shots must depict the exact same character\n"
        "Always end with the consistency and no text line\n\n"
        "Important rules:\n"
        "- For minor characters with minimal description, keep the prompt shorter but still fully specified.\n"
        "- For major characters, provide more detailed prompts.\n"
        "- Do NOT leave fields blank.\n\n"
        "Version consistency rules:\n"
        "- Each character entry may include an identity_anchor, version_label, and appears_from.\n"
        "- If identity_anchor is present, it describes stable facial / anatomical traits that MUST stay consistent "
        "across every version of this character. Preserve these traits in the generated prompt.\n"
        "- If version_label and appears_from are present, the prompt must reflect this specific life-stage only.\n"
        "- Do NOT mix traits from different versions into the same prompt.\n\n"
        'Return ONLY a JSON object with a top-level "characters" array; each element has fields: name, turnaround_prompt.'
    )
    user = f"<characters>\n{_to_json_str(characters)}\n</characters>"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_segment_breakdown_messages(script: str, words: str) -> list[dict]:
    """§5.2 Pass 1 — Segment breakdown (style-invariant)."""
    system = (
        "You are a video editor. You are given a full script and the word-level timestamps from the voiceover.\n"
        "Your task is to break the script into logical segments.\n\n"
        "Rules for segment breaks:\n"
        "1. Each segment should cover one visual \"beat\" or scene.\n"
        "2. A segment can contain one or more sentences.\n"
        "3. Short sentences (≤10 words) that describe the same scene should be merged into one segment.\n"
        "4. Long sentences that describe multiple visual beats should be split.\n"
        "5. A scene transition (change in location, time of day, or major action) always starts a new segment.\n"
        "6. A pause of ≥1.5 seconds in the voiceover should start a new segment.\n"
        "7. Each segment must have a start_time and end_time based on the word timestamps.\n"
        "8. Aim for segment durations of 3–10 seconds. Avoid segments shorter than 2 seconds unless necessary.\n\n"
        'Output a JSON object with a top-level "segments" array, where each element has:\n'
        "- segment_index: int\n"
        "- script_line: the text for this segment\n"
        "- start_time: float (seconds)\n"
        "- end_time: float (seconds)\n"
        "- duration: float (computed)\n\n"
        "Return ONLY the JSON object."
    )
    user = (
        f"<script>\n{script}\n</script>\n\n"
        f"<word_timestamps>\n{words}\n</word_timestamps>"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_segment_prompts_messages(
    segments_batch: object, characters: object, style: StyleProfile
) -> list[dict]:
    """§5.2 Pass 2 — Segment prompt generation."""
    shot_types_line = ", ".join(SHOT_TYPES)
    system = (
        "You are a scene director and cinematographer for a narrative YouTube video.\n"
        "You are generating image prompts for an AI image generator (Gemini/Flow).\n\n"
        "For each segment, read the script line and the character profiles.\n"
        "Generate a vivid, detailed image generation prompt.\n\n"
        "## Output Format\n\n"
        "For each segment, output:\n"
        "- segment_index: int\n"
        "- script_line: str\n"
        "- segment_prompt: str\n"
        '- characters_present: List[str] (e.g., ["@Alice", "@Bob"])\n'
        "Every output item MUST include segment_index — this field is required for correct downstream matching.\n\n"
        "## Rules for segment_prompt\n\n"
        "1. **Opening style anchor:** Every prompt must start with style descriptors that match the video's visual identity.\n"
        f'   - Example: "{style.segment_scene_anchor}"\n\n'
        "2. **Scene description:** Describe the setting, lighting, atmosphere, and mood.\n"
        "   - Include specific lighting: golden hour, twilight, harsh midday, moonlight, candlelight, etc.\n"
        "   - Include atmosphere: fog, mist, rain, dust, snow, heat shimmer.\n"
        "   - Use shot selection based on the content:\n"
        "     - Landscapes / establishing scenes → wide shot or extreme wide shot\n"
        "     - Emotional character moments → close-up or medium shot\n"
        "     - Action / movement → medium shot or over-the-shoulder\n"
        "     - Objects / details → close-up or extreme close-up\n\n"
        "3. **Character placement:** If characters are present, describe their:\n"
        "   - Position in the frame (center, foreground, background, left-third)\n"
        "   - Action / pose (walking, sitting, looking away, mid-stride, reaching out)\n"
        "   - Expression (worried, determined, joyful, terrified)\n"
        "   - Clothing reference (use the character's description from the profile)\n"
        "   - Do NOT copy the full character profile — describe them concisely in the scene context.\n\n"
        "4. **Camera and framing:**\n"
        f"   - Shot type: {shot_types_line}\n"
        "   - Lens feel: shallow depth of field, deep focus, telephoto compression, wide-angle distortion.\n"
        "   - Movement implication: static, tracking, handheld, dolly-in.\n"
        "   - Note: Since the final image is static (with motion effects applied later), describe the image as a key frame from the chosen camera position.\n\n"
        "5. **Color palette and grading:**\n"
        "   - Describe the dominant color palette: warm desaturated, cool blue-teal, high-contrast noir, vibrant saturated, muted earth tones.\n"
        "   - Mention lighting color temperature if relevant.\n\n"
        "6. **Negative constraints:** End with \"no text, no watermark, no logo, no UI elements.\"\n\n"
        "7. **Length:** Keep prompts to 3–6 lines, comma-separated. Rich detail but not a novel.\n\n"
        "8. **Character references:**\n"
        "   - If a character is visually present in the segment, include their name in characters_present as @Name.\n"
        '   - If a character is mentioned but not shown (e.g., "Alice thought about Bob"), do NOT include @Bob unless Bob is visible in the scene.\n\n'
        "9. **Version resolution:**\n"
        "   - Characters may have multiple visual versions across narrative time (e.g., age stages, transformations).\n"
        "   - For each character present in a segment, pick the version whose appears_from boundary the segment's script_line falls into.\n"
        "   - Judge based on this segment's own content. Do NOT assume versions change in segment order — flashbacks may revisit earlier versions.\n"
        "   - Put the resolved version's unique name in characters_present and describe that version's traits in the prompt.\n\n"
        "10. **Consistency:**\n"
        "   - Maintain visual consistency within a character version. When the script crosses a version boundary (e.g., a time skip or transformation), "
        "switch deliberately to the new version's appearance; do not carry the old appearance across the boundary, and do not change appearance without a boundary.\n\n"
        "## Example Good Prompt\n\n"
        'script_line: "Alice walked through the dark forest, her heart pounding."\n'
        'segment_prompt: "Cinematic wide shot, photorealistic 3D render, Secret Level / Love Death and Robots style, highly detailed, cinematic lighting. '
        "A dark enchanted forest at twilight, ancient gnarled trees with twisted branches, dense fog rolling between the trunks, "
        "faint golden moonlight filtering through the canopy. Alice in the foreground, center-left, walking cautiously on a moss-covered path, "
        "her red wool coat visible, determined yet worried expression, arms slightly out for balance. Shallow depth of field, background trees blurred into dark silhouettes. "
        "Cool blue-green palette with warm highlights from moonlight. Atmospheric, tense, mysterious. no text, no watermark, no logo.\"\n\n"
        "## Example Bad Prompt\n\n"
        'script_line: "Alice walked through the dark forest, her heart pounding."\n'
        'segment_prompt: "A forest. Alice walking. Trees."  ❌ TOO VAGUE\n\n'
        f'segment_prompt: "{style.negative_style_example}"  ❌ WRONG STYLE\n\n'
        'segment_prompt: "A dark forest at twilight. Ancient gnarled trees with twisted branches. Dense fog rolling between the trunks. '
        "Faint golden moonlight filtering through the canopy. Alice in the foreground, center-left, walking cautiously on a moss-covered path. "
        "Her red wool coat visible. Determined yet worried expression. Arms slightly out for balance. Shallow depth of field. Background trees blurred into dark silhouettes. "
        "Cool blue-green palette with warm highlights from moonlight. Atmospheric, tense, mysterious. No text, no watermark, no logo.\"  ❌ TOO LONG AND SENTENCE-BASED\n\n"
        "## Character Profile Usage\n\n"
        "You are provided with the character list (name, description, front_profile_prompt, turnaround_prompt).\n"
        "When a character appears in a segment:\n"
        "1. Extract their key visual traits from the description (hair, clothing, build, expression)\n"
        '2. Describe them briefly in the scene context (e.g., "Alice in her red wool coat, determined expression")\n'
        "3. Do NOT paste the full profile prompt into the segment prompt\n"
        "4. Tag them in characters_present as @Name\n\n"
        'Return ONLY a JSON object with a "segments" array.'
    )
    user = (
        f"<segments>\n{_to_json_str(segments_batch)}\n</segments>\n\n"
        f"<characters>\n{_to_json_str(characters)}\n</characters>"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
