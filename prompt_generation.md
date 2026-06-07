# Prompt Generation Accuracy Report

**Status:** Critical — Implementation prompts are bare-bones stubs while `DESIGN_SPEC.md` specifies production-ready, detailed prompts.

**Affected Files:**
- `backend/routers/characters.py` (Call 1 extraction + Call 2 prompt generation)
- `backend/routers/segments.py` (Pass 1 breakdown + Pass 2 prompt generation)

**Source of Truth:** `DESIGN_SPEC.md` §4.1, §4.2, §5.2

---

## 1. Character Extraction — Call 1 (`characters.py:98-103`)

### What the Code Does
```python
"Extract all characters from the following script. "
"For each character, provide: name, type (e.g., protagonist, antagonist, supporting), "
"importance (e.g., main, minor, background), and a brief description. "
"Return ONLY valid JSON matching the requested schema.\n\n"
f"{script_content}"
```

### What DESIGN_SPEC.md §4.1 Requires
- **Role:** "You are a **character extraction engine**"
- **Extraction scope:**
  1. Named speaking characters (e.g., "Alice", "Bob")
  2. Significant NPCs or creatures that appear visually (e.g., "the dragon")
  3. Any NPC entity that has a visual presence
- **Type enum:** `speaking` | `creature` | `npc_entity`
- **Importance enum:** `major` | `minor`
- **Description rule:** Detailed visual description; infer a visually interesting design if script doesn't describe them; **do NOT leave fields blank**
- **XML tags:** `<system>`, `<script>`

### Key Discrepancies
| DESIGN_SPEC.md | Code | Impact |
|---|---|---|
| Role: "character extraction engine" | No role assignment | AI may not know its task |
| Type: `speaking` / `creature` / `npc_entity` | Generic: `protagonist` / `antagonist` / `supporting` | Wrong schema values, may break downstream |
| Importance: `major` / `minor` | Generic: `main` / `minor` / `background` | Extra invalid enum value, missing `major` |
| Description: "detailed visual, infer if blank, never leave empty" | "brief description" | AI may output short/vague descriptions |
| XML `<system>` + `<script>` tags | No tags, just raw text concatenation | No structured context for the AI |

---

## 2. Character Prompt Generation — Call 2 (`characters.py:190-206`)

### What the Code Does
```python
"For each character below, generate two prompts:"
"1. front_profile_prompt: A detailed description of the character's face from the front..."
"2. turnaround_prompt: A detailed description of the character's appearance from all angles..."
"Return ONLY valid JSON matching the requested schema."

"Characters:"
for char in characters:
    prompt_lines.append(f"- {name} ({importance} {char_type}): {description}")
```

### What DESIGN_SPEC.md §4.2 Requires
- **Role:** "You are a character art prompt writer for an animated series in the visual style of Secret Level and Love Death and Robots."
- **Style anchors (mandatory opening lines):**
  - Front Profile: "Secret Level / Love Death and Robots style animation, photorealistic 3D render, cinematic lighting, subsurface skin scattering..."
  - Turnaround: "Secret Level / Love Death and Robots style animation, photorealistic 3D render, character turnaround reference sheet, professional character modeling sheet..."
- **Detailed append order:** Age → Gender → Hair → Skin → Eye → Face → Outfit → Lower body → Shot type → Background → No text
- **Turnaround structure:** Three-view turnaround + six head-angle references + six close-up detail shots with specific instructions
- **Rules:** 2-4 lines max, comma-separated, no full sentences, no anime/cel-shading, hybrid character handling, always end with background/no-text
- **XML tags:** `<system>`, `<characters>`

### Key Discrepancies
| DESIGN_SPEC.md | Code | Impact |
|---|---|---|
| Role + style anchor | No role, no style anchor | AI won't know the target visual style |
| "Secret Level / Love Death and Robots" | Not mentioned | Generated prompts won't match the aesthetic |
| Detailed append order (9 fields) | No structure specified | AI will generate random/unstructured prompts |
| Turnaround: 3-view + 6 head angles + 6 close-ups | Just says "360-degree turnaround" | Missing reference sheet structure |
| 2-4 lines, comma-separated, no sentences | No formatting rules | Prompts may be too long, sentence-based, verbose |
| No anime/cel-shading prohibition | No style prohibition | AI may output wrong style |
| `<system>` + `<characters>` XML tags | No XML tags, plain list | No structured context for the AI |
| Hybrid/non-humanoid handling | No instructions | AI will default to human shoe/clothing details |

---

## 3. Segment Breakdown — Pass 1 (`segments.py:207-216`)

### What the Code Does
```python
"You are given a voiceover script and a list of transcribed words with timestamps. "
"Break the script into logical segments (e.g., sentences or phrases). "
"For each segment, provide the exact script line, the start time, the end time, and the duration. "
"Return the result as a JSON object with a 'segments' array."

"Script:\n" + script_text + "\n\n"
"Words with timestamps:\n" + json.dumps(words, indent=2)
```

### What DESIGN_SPEC.md §5.2 Requires
- **Role:** "You are a **video editor**" (not "helpful assistant")
- **8 explicit segment break rules:**
  1. One visual "beat" or scene per segment
  2. One or more sentences per segment
  3. Short sentences (≤10 words) → merge if same scene
  4. Long sentences → split on multiple visual beats
  5. Scene transition → always new segment
  6. Pause ≥1.5 seconds → new segment
  7. start_time/end_time from word timestamps
  8. Target duration 3–10 seconds, avoid <2 seconds
- **XML tags:** `<system>`, `<script>`, `<word_timestamps>`
- **Output fields:** `segment_index`, `script_line`, `start_time`, `end_time`, `duration`

### Key Discrepancies
| DESIGN_SPEC.md | Code | Impact |
|---|---|---|
| Role: "video editor" | Generic "You are given..." | AI may not optimize for video editing logic |
| 8 explicit break rules | No rules at all | AI may create segments that are too short, too long, or break mid-scene |
| Duration guidance: 3–10s, avoid <2s | No guidance | Segments may be suboptimal for video pacing |
| `<system>` + `<script>` + `<word_timestamps>` | No XML tags | No structured context |
| Scene transition / pause rules | No mention | AI won't know to break on scene changes or pauses |

---

## 4. Segment Prompt Generation — Pass 2 (`segments.py:107-127`)

### What the Code Does
```python
"You are given a list of video segments and a list of characters. "
"For each segment, generate an image generation prompt that describes the visual scene, "
"and identify which characters from the character list are present in that segment. "
"Return the result as a JSON object with a 'segments' array."

"Characters:\n" + json.dumps(characters, indent=2) + "\n\n"
"Segments:\n" + json.dumps(segments_batch, indent=2)
```

### What DESIGN_SPEC.md §5.2 Requires
- **Role:** "You are a **scene director and cinematographer** for a narrative YouTube video"
- **9 explicit prompt construction rules:**
  1. Opening style anchor ("Cinematic wide shot, photorealistic 3D render...")
  2. Scene description with specific lighting/atmosphere
  3. Character placement (position, action, expression, clothing)
  4. Camera and framing (shot type, lens feel, movement)
  5. Color palette and grading
  6. Negative constraints ("no text, no watermark, no logo, no UI elements")
  7. Length: 3–6 lines, comma-separated
  8. Character references: `@Name` format, visibility check
  9. Consistency across segments (lighting, palette, atmosphere)
- **Example good/bad prompts** to train the model
- **Character profile usage guidelines** (don't paste full profile, extract key traits)
- **XML tags:** `<system>`, `<segments>`, `<characters>`

### Key Discrepancies
| DESIGN_SPEC.md | Code | Impact |
|---|---|---|
| Role: "scene director and cinematographer" | Generic "You are given..." | AI may not optimize for cinematic quality |
| Opening style anchor | No style anchor | Prompts won't match the target visual identity |
| 9 explicit prompt rules | No rules at all | AI will generate generic, unstructured prompts |
| Negative constraints | No constraints | AI may include text, watermarks, UI elements |
| Length: 3–6 lines, comma-separated | No guidance | Prompts may be too short or too long |
| `@Name` format for characters | No mention | Character references may not use the required format |
| Consistency rule across segments | No mention | Lighting/atmosphere may vary wildly between segments |
| Example good/bad prompts | No examples | AI has no reference for what quality looks like |
| Character profile usage: "don't paste full profile" | No instruction | AI may dump entire profile prompts into segments |
| `<system>` + `<segments>` + `<characters>` | No XML tags | No structured context |

---

## Summary

| # | Prompt | File | Severity | Main Issue |
|---|--------|------|----------|------------|
| 1 | Character Extraction (Call 1) | `characters.py:98-103` | **High** | Wrong type/importance enums, no role, no XML tags, no description rules |
| 2 | Character Prompt Generation (Call 2) | `characters.py:190-206` | **High** | No style anchor, no append order, no turnaround structure, no formatting rules |
| 3 | Segment Breakdown (Pass 1) | `segments.py:207-216` | **High** | No 8 break rules, no duration guidance, no XML tags |
| 4 | Segment Prompt Generation (Pass 2) | `segments.py:107-127` | **High** | No 9 prompt rules, no style anchor, no examples, no negative constraints, no `@Name` format |

All four prompts are **bare-bones stubs** that omit the critical structured guidance, rules, examples, and XML tags defined in `DESIGN_SPEC.md`. The AI will produce generic, unstructured output that doesn't match the intended visual style, segment quality, or character consistency. This is a systemic gap across the entire AI prompt layer.

---

## Recommended Action

1. **Rewrite all four prompts** to match `DESIGN_SPEC.md` exactly
2. **Use XML tag structure** (`<system>`, `<script>`, `<characters>`, `<segments>`, `<word_timestamps>`)
3. **Include all rules, examples, and constraints** from the spec
4. **Update backend tests** to verify the prompt content (or at least verify the AI receives the correct schema)
5. **Consider adding prompt templates** to `services/fireworks.py` or a dedicated `services/prompts.py` module to keep router files clean and make prompts versionable

---

*Report generated against:*
- `DESIGN_SPEC.md` §4.1, §4.2, §5.2
- `backend/routers/characters.py` (lines 98-103, 190-206)
- `backend/routers/segments.py` (lines 107-127, 207-216)
