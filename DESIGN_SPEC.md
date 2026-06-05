# Conduit — Design Specification

*A narrative story video generation tool for YouTube.*

**Version:** 1.0  
**Date:** 2026-06-02  
**Status:** Final (post-grill)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Step 1: Script — Voiceover → Transcription → Source of Truth](#3-step-1-script--voiceover--transcription--source-of-truth)
4. [Step 2: Character Profiles](#4-step-2-character-profiles)
5. [Step 3: Segment Prompts](#5-step-3-segment-prompts)
6. [Step 4: Image Uploading](#6-step-4-image-uploading)
7. [Step 5: Video Generation](#7-step-5-video-generation)
8. [Data Model & Project State](#8-data-model--project-state)
9. [Tech Stack](#9-tech-stack)
10. [Deployment](#10-deployment)
11. [Security](#11-security)
12. [Error Handling](#12-error-handling)
13. [Open Questions](#13-open-questions)

---

## 1. Project Overview

**Name:** Conduit  
**Type:** Web application (personal tool, local deployment)  
**User:** Single user (creator)  
**Goal:** Turn a voiceover + optional script into a 1080p 24fps YouTube video with AI-generated scene images, motion effects, and burned captions.

### UI Navigation Pattern

**Wizard with Next/Back buttons.** Linear step-by-step flow.

- User must complete Step 1 before proceeding to Step 2
- Step 2 must be completed before Step 3
- And so on
- Each step has a **Next** button (enabled when prerequisites are met) and a **Back** button (to return to previous step)
- **Step 1 Next button:** Enabled when transcript is present (frontend state), regardless of backend `step_1_complete`. If original script is present and fidelity < 95%, pressing Next shows a non-blocking warning modal with "Review Anyway" and "Continue Reviewing" options.
- Progress indicator at the top: Step 1 → Step 2 → Step 3 → Step 4 → Step 5

**Cascade Rule:** If the user clicks **Back** to a previous step and makes any edit, all **downstream steps are automatically invalidated** and must be re-run.
- Example: Editing Step 2 (characters) clears Step 3 (segments), Step 4 (images), and Step 5 (video)
- The UI shows a warning: "You edited Step 2. Steps 3–5 have been reset. Please regenerate them."
- This ensures consistency: no stale segment prompts referencing old character descriptions, no mismatched images, etc.
- Images uploaded in Step 4 are preserved (still on disk) but the segment data is cleared, so the user must re-upload mappings after regenerating Step 3

### Five-Step Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: SCRIPT                                                      │
│  Voiceover → Whisper API → Transcript + Word-Level Timestamps       │
│  ↓ + Optional Original Script → AI Cross-Reference                   │
│  Source of Truth Script (JSON)                                      │
│  [Next →]                                                            │
├─────────────────────────────────────────────────────────────────────┤
│  STEP 2: CHARACTER PROFILES                                          │
│  AI analyzes source of truth script → Extracts characters            │
│  Each character gets: name + profile_prompt (for Gemini/Flow)       │
│  Output: JSON + rendered cards with copy-paste prompts             │
│  [← Back]  [Next →]                                                  │
├─────────────────────────────────────────────────────────────────────┤
│  STEP 3: SEGMENT PROMPTS                                             │
│  AI analyzes script + timestamps + characters                      │
│  Generates: segment prompts (scene descriptions)                   │
│  Output: table of segments with prompts, character refs, script lines│
│  [← Back]  [Next →]                                                  │
├─────────────────────────────────────────────────────────────────────┤
│  STEP 4: IMAGE UPLOADING                                             │
│  Grid view of all segments. Upload PNG images per segment.           │
│  Placeholder for missing images. "Details" shows metadata.          │
│  [← Back]  [Next →]                                                  │
├─────────────────────────────────────────────────────────────────────┤
│  STEP 5: VIDEO GENERATION                                            │
│  Random motion effects per segment. Optional caption burn. Generate. │
│  Output: 1080p 24fps MP4. Download.                                  │
│  [← Back]  [Generate Video]  [Download]                               │
└─────────────────────────────────────────────────────────────────────┘
```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: SCRIPT                                                      │
│  Voiceover → Whisper API → Transcript + Word-Level Timestamps       │
│  ↓ + Optional Original Script → AI Cross-Reference                   │
│  Source of Truth Script (JSON)                                      │
├─────────────────────────────────────────────────────────────────────┤
│  STEP 2: CHARACTER PROFILES                                          │
│  AI analyzes source of truth script → Extracts characters            │
│  Each character gets: name + profile_prompt (for Gemini/Flow)       │
│  Output: JSON + rendered cards with copy-paste prompts               │
├─────────────────────────────────────────────────────────────────────┤
│  STEP 3: SEGMENT PROMPTS                                             │
│  AI analyzes script + timestamps + characters + reference book     │
│  Generates: segment prompts (scene descriptions)                   │
│  Output: table of segments with prompts, character refs, script lines│
├─────────────────────────────────────────────────────────────────────┤
│  STEP 4: IMAGE UPLOADING                                             │
│  Grid view of all segments. Upload PNG images per segment.           │
│  Placeholder for missing images. "Details" shows metadata.          │
├─────────────────────────────────────────────────────────────────────┤
│  STEP 5: VIDEO GENERATION                                            │
│  Select motion effects per segment. Burn captions. Generate.         │
│  Output: 1080p 24fps MP4. Download.                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture

### Deployment Decision

**Local web application** — runs on the user's laptop (RTX 3060M). Not deployed to Railway.

Reasoning:
- Railway's ephemeral storage requires persistent volumes; local storage is simpler
- No HTTP timeout issues for long ffmpeg renders
- No need for background job queues or polling
- File uploads are local (fast, no network overhead)
- 150–250 images per 15-minute video are easier to manage locally
- No auth needed (single user, localhost)
- Can use ffmpeg and GPU directly without Docker complexity

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Web UI)                         │
│         React/Vue/Svelte — Browser-based                     │
│              Accessed via http://localhost:8000              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP / REST (localhost)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                             │
│         Python 3.12+ — Async — Localhost                     │
│                                                              │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │  Whisper    │  │  Fireworks AI   │  │    ffmpeg       │   │
│  │  API Client │  │  (FirePass)     │  │    Pipeline     │   │
│  │  (openai)   │  │  (openai SDK)   │  │    (subprocess) │   │
│  └─────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                              │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │  srt/pysubs2│  │  pydub          │  │  SQLite/JSON    │   │
│  │  (SRT/ASS)  │  │  (audio chunk)  │  │  (project state)│   │
│  └─────────────┘  └─────────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### API Providers

| Provider | Role | Endpoint | Model |
|----------|------|----------|-------|
| **OpenAI** | Speech-to-text | `https://api.openai.com/v1/audio/transcriptions` | `whisper-1` |
| **Fireworks AI (FirePass)** | LLM analysis | `https://api.fireworks.ai/inference/v1` | `accounts/fireworks/routers/kimi-k2p6-turbo` |

### Why These Choices?

- **Whisper API** over local: simpler, no GPU dependency needed, no model setup.
- **Fireworks AI** over OpenAI: user's preferred provider (FirePass), OpenAI-compatible SDK, supports `json_schema` structured outputs.
- **ffmpeg** over MoviePy: 10–50x faster for 1080p, memory-efficient, no Python frame I/O overhead.
- **Local FastAPI** over Railway: simpler, no timeout limits, no auth, direct filesystem access.
- **Web app over CLI:** user explicitly wants a grid UI for image uploads and a visual step-by-step workflow.

---

## 3. Step 1: Script — Voiceover → Transcription → Source of Truth

### 3.1 Input: Voiceover Audio

| Property | Value |
|----------|-------|
| **Accepted formats** | MP3, WAV, M4A |
| **Channels** | Mono (preferred) or stereo (auto-mix to mono before Whisper) |
| **Typical length** | 1–60 minutes (YouTube narrative videos) |
| **File size limit** | 25 MB per Whisper API request |
| **Chunking strategy** | **Auto-chunk** with `pydub` on silence boundaries (≥300ms silence) |

**Auto-chunk logic:**
1. Load audio with `pydub.AudioSegment`
2. Detect silence ≥ 300ms
3. Split into chunks, each ≤ 25 MB (or ≤ 20 MB for safety margin)
4. Ensure splits happen at sentence boundaries, not mid-word
5. Send each chunk to Whisper API in parallel
6. Merge word-level JSON arrays in order

### 3.2 Whisper API Call

```python
client = OpenAI()  # OpenAI API key

response = client.audio.transcriptions.create(
    model="whisper-1",              # ONLY model that supports word-level timestamps
    file=audio_chunk,
    response_format="verbose_json",  # Required for word-level output
    timestamp_granularities=["word"] # Returns words[] with start, end, word
)
```

**Output format per chunk:**
```json
{
  "words": [
    {"word": "It",    "start": 0.000, "end": 0.120},
    {"word": "was",   "start": 0.180, "end": 0.300},
    {"word": "the",   "start": 0.360, "end": 0.420},
    {"word": "best",  "start": 0.480, "end": 0.660},
    {"word": "of",    "start": 0.720, "end": 0.780},
    {"word": "times", "start": 0.840, "end": 1.020}
  ]
}
```

### 3.3 SRT Generation

**Grouping strategy:** Natural sentence/phrase boundaries.

- Split at punctuation (`.`, `?`, `!`)
- Keep each line ≤ 42 characters for readability
- 1–2 sentences per caption line
- Never split mid-word

**Example:**
```
1
00:00:00,000 --> 00:00:01,500
It was the best of times.

2
00:00:01,500 --> 00:00:03,200
It was the worst of times.
```

**Implementation:**
- Build SRT from the merged `words` array
- Use `srt` library to validate and sort
- Also save the raw `words` array as `words.json` for precise segment timing

### 3.4 Optional: Original Script Input

| Property | Value |
|----------|-------|
| **Format** | Markdown (`.md`) |
| **Content** | Dialogue, voiceover text, stage directions |
| **Optional** | Yes — user can skip this and use the raw transcript |
| **Purpose** | Ground truth for AI cross-reference correction |

### 3.5 AI Cross-Reference: Two-Step Process

**Goal:** Produce a corrected "source of truth" script by reconciling the Whisper transcript against the original script.

#### Step 1a: Identify Differences

Send both texts to Fireworks AI with a structured prompt:

```xml
<system>
You are a transcript editor. Compare the voiceover transcript against the original script.
Identify all differences: transcription errors, filler words, omissions, and paraphrasing.

Also identify structural markers that are NOT spoken in the voiceover and should be removed:
- Section headers (e.g., "Chapter 1", "Introduction", "Part 1")
- Speaker labels (e.g., "NARRATOR:", "HOST:")
- Stage directions (e.g., "[sighs]", "[pause]")
- Formatting markers (e.g., "---", "TITLE CARD", "END")

Treat these as intentional omissions — they should NOT appear in the final source of truth script.
</system>

<voiceover_transcript>
{whisper_transcript}
</voiceover_transcript>

<original_script>
{user_script}
</original_script>

Return a JSON array of differences. Each entry must have:
- type: "correction" | "omission" | "addition" | "filler_removed"
- transcript_text: the word(s) from the voiceover
- script_text: the corresponding word(s) from the original script
- corrected_text: the final chosen word(s)
- reason: why this change was made
- confidence: 0.0–1.0
```

**Output schema:**
```python
class TextChange(BaseModel):
    type: str
    transcript_text: Optional[str]
    script_text: Optional[str]
    corrected_text: str
    reason: str
    confidence: float

class Differences(BaseModel):
    changes: List[TextChange]
```

#### Step 1b: Present to User for Approval

- Show the differences in a diff UI (like GitHub diff)
- User can approve, reject, or edit each change
- Approved changes are locked in
- **Fidelity percentage badge** — displayed in diff header, real-time calculation: `(equal words + approved changes) / total script words × 100`. Color-coded: green ≥95%, amber 80–94%, red <80%. Provides at-a-glance metric of transcript faithfulness.
- **Auto-Approve button** — "Approve Remaining" in diff header (ghost style) bulk-approves all unreviewed changes without overriding rejections. Disabled when no unreviewed changes remain.

#### Step 1c: Quality Gate (Next Button)

- **Next button logic:** Enabled when transcript is present (frontend state), regardless of backend completion status.
- **Warning modal:** If original script is present and fidelity < 95%, pressing Next shows a non-blocking warning modal explaining the fidelity gap. User can choose "Review Anyway" (proceeds to Step 2) or "Continue Reviewing" (closes modal, stays on Step 1).
- **No original script:** Next proceeds immediately without warning.

#### Step 1d: Generate Source of Truth Script

- Merge all approved changes into a single corrected text
- Save as `source_of_truth_script.txt`

### 3.6 No Original Script Provided

If the user does NOT provide an original script:
1. Run a **light AI pass** on the Whisper transcript
2. Remove obvious filler words ("um", "uh", "like", "you know")
3. Fix obvious transcription errors (homophones: "there/their", "its/it's")
4. Save the cleaned transcript as `source_of_truth_script.txt`

### 3.7 Output of Step 1

| File | Description |
|------|-------------|
| `words.json` | Word-level timestamps from Whisper |
| `captions.srt` | Generated SRT for burning |
| `transcript_raw.txt` | Raw Whisper transcript (unedited) |
| `source_of_truth_script.txt` | Final corrected script for downstream |

---

## 4. Step 2: Character Profiles

**Mandatory step.** Every story has characters, so this step is always required. There is no skip option.

Step 2 is split into **two distinct LLM calls** to separate character understanding from prompt generation.

### 4.1 Call 1 — Character Extraction

**Goal:** Read the script and extract all visually important entities with descriptions.

**Prompt:**
```xml
<system>
You are a character extraction engine. Read the script and identify all entities that are visually important in the story.

Extract:
1. Named speaking characters (e.g., "Alice", "Bob")
2. Significant NPCs or creatures that appear visually (e.g., "the dragon", "the old merchant")
3. Any NPC entity that has a visual presence

For each entity, output:
- name: the canonical name
- type: "speaking" | "creature" | "npc_entity"
- importance: "major" if the entity appears in multiple scenes or is central to the plot. "minor" if they appear once or are background.
- description: a detailed visual description of the character's appearance, clothing, and expression. If the script does not describe them in detail, infer a visually interesting design that fits the narrative. Do NOT leave fields blank.
</system>

<script>
{source_of_truth_script}
</script>
```

**Output schema:**
```python
class CharacterDescription(BaseModel):
    name: str
    type: str  # "speaking" | "creature" | "npc_entity"
    importance: str  # "major" | "minor"
    description: str

class CharacterList(BaseModel):
    characters: List[CharacterDescription]
```

**UI after Call 1:**
- Table of extracted characters with name, type, importance, and description
- **User can edit descriptions** before proceeding
- **Generate Prompts button** triggers Call 2

### 4.2 Call 2 — Prompt Generation

**Goal:** Generate front_profile_prompt and turnaround_prompt for each character using the finalized descriptions.

**Prompt:**
```xml
<system>
You are a character art prompt writer for an animated series in the visual style of Secret Level and Love Death and Robots.

For each character in the list, generate TWO prompts:

Prompt A — Front Profile:
Style anchors (always include):
Secret Level / Love Death and Robots style animation, photorealistic 3D render, cinematic lighting, subsurface skin scattering, physically based rendering, hyper-detailed face, face depth, realistic eyes, volumetric lighting, sharp detailed textures, clean render
Then append in this order:
Age, gender, race or species type
Hair description (length, style, color, texture)
Skin tone and build
Eye description (color, shape, expression)
Face shape and expression
Outfit or upper body description
Lower body or full body description if non-humanoid
Shot type and framing
Background
no text, no watermark, no logo
Rules:
Keep prompts to 2-4 lines maximum, comma-separated, no full sentences
Never use anime or cel-shading language
For hybrid or monster characters, describe the non-human parts with precise anatomical and material detail
Always end with background description and no text

Prompt B — Turnaround Reference Sheet:
Always open with:
Secret Level / Love Death and Robots style animation, photorealistic 3D render, character turnaround reference sheet, professional character modeling sheet, cinematic lighting, subsurface skin scattering, physically based rendering, hyper-detailed face, face depth, realistic eyes, sharp detailed textures, clean render, pure white background, landscape composition, no text, no watermark, no logo
Then append in this order:
Age, gender, race or species type
Hair description (length, style, color, texture)
Skin tone and build
Eye description (color, shape, expression)
Face shape and expression
Outfit or upper body description
Lower body or full body if non-humanoid
Three-view turnaround instruction: left side of composition shows three full-body views — front, left-side profile, and back — same character, identical proportions, natural standing pose, arms at sides, eye-level camera
Upper-right instruction: upper-right section shows six head-angle references — front-facing, slight downward, back of head, left-side profile, near-side comparison, 3/4 profile
Lower-right instruction: lower-right section shows six close-up detail shots — upper garment texture, lower body clothing, hip detail, leg or skin texture, eyes and facial features, full shoe close-up
strict character consistency throughout, no cropping, no extra props, no text, no logo, no watermark
Rules:
Keep the character description portion to 2-4 lines, comma-separated, no full sentences
Never use anime or cel-shading language
For non-humanoid or hybrid characters, replace shoe/clothing detail shots with anatomically appropriate equivalents
All three turnaround views and all detail shots must depict the exact same character
Always end with the consistency and no text line

Important rules:
- For minor characters with minimal description, keep the prompt shorter but still fully specified.
- For major characters, provide more detailed prompts.
- Do NOT leave fields blank.
</system>

<characters>
{character_list_with_descriptions}
</characters>
```

**Output schema:**
```python
class CharacterPrompts(BaseModel):
    name: str
    front_profile_prompt: str
    turnaround_prompt: str

class CharacterPromptsList(BaseModel):
    characters: List[CharacterPrompts]
```

### 4.3 UI Presentation

- **Dropdown:** Select AI model (for image generation) — this is just a UI label; no actual model is called here
- **Step 1 — Extract Characters button:** Triggers Call 1 (extraction)
- **Step 2 — Generate Prompts button:** Triggers Call 2 (prompt generation, enabled after editing)
- **Display after Call 2:** Cards for each character
  - Name
  - Type badge (speaking / creature / npc_entity)
  - Importance badge (major / minor)
  - **Front Profile Prompt** — copy-paste ready for Gemini/Flow (single image)
  - **Turnaround Reference Prompt** — copy-paste ready for Gemini/Flow (reference sheet)
- **JSON View:** Toggle to see raw JSON

### 4.3 Output

**After Call 1 (extraction):**
| File | Description |
|------|-------------|
| `characters.json` | Extracted characters with descriptions (no prompts yet) |

**After Call 2 (prompt generation):**
| File | Description |
|------|-------------|
| `characters.json` | Extracted characters with front_profile_prompt and turnaround_prompt |

**State tracking:**
- `step_2_call_1_completed`: true after extraction
- `step_2_call_2_completed`: true after prompt generation

---

## 5. Step 3: Segment Prompts

### 5.1 Segment Definition

| Property | Value |
|----------|-------|
| **Unit** | Per sentence, but AI decides smart breaks based on context |
| **Smart logic** | Short sentences → 1 segment. Long sentences / complex beats → AI may split into 2+ segments. Pauses → new segment. |
| **Timing** | Each segment gets `start_time` and `end_time` from the word-level timestamps |

**Example:**
```
Script: "It was the best of times. It was the worst of times."
→ Segment 1: "It was the best of times." (0.0s → 3.2s)
→ Segment 2: "It was the worst of times." (3.2s → 6.5s)
```

```
Script: "Alice walked through the dark forest, her heart pounding, until she saw the light."
→ AI may split:
   Segment 1: "Alice walked through the dark forest, her heart pounding," (0.0s → 5.0s)
   Segment 2: "until she saw the light." (5.0s → 7.5s)
```

### 5.2 AI Prompt for Segment Generation

The segment generation process uses **two distinct passes**:

1. **Segment Breakdown Pass** — determines where segments start and end
2. **Segment Prompt Generation Pass** — generates the image prompt for each segment

Both passes use the same context but serve different purposes.

---

#### Pass 1: Segment Breakdown

**Goal:** Break the source-of-truth script into logical segments, each with timing from the word-level timestamps.

**Prompt:**
```xml
<system>
You are a video editor. You are given a full script and the word-level timestamps from the voiceover.
Your task is to break the script into logical segments.

Rules for segment breaks:
1. Each segment should cover one visual "beat" or scene.
2. A segment can contain one or more sentences.
3. Short sentences (≤10 words) that describe the same scene should be merged into one segment.
4. Long sentences that describe multiple visual beats should be split.
5. A scene transition (change in location, time of day, or major action) always starts a new segment.
6. A pause of ≥1.5 seconds in the voiceover should start a new segment.
7. Each segment must have a start_time and end_time based on the word timestamps.
8. Aim for segment durations of 3–10 seconds. Avoid segments shorter than 2 seconds unless necessary.

Output a JSON array of segments with:
- segment_index: int
- script_line: the text for this segment
- start_time: float (seconds)
- end_time: float (seconds)
- duration: float (computed)

Return ONLY the JSON object.
</system>

<script>
{source_of_truth_script}
</script>

<word_timestamps>
{words.json}
</word_timestamps>
```

**Output schema:**
```python
class SegmentBreakdown(BaseModel):
    segment_index: int
    script_line: str
    start_time: float
    end_time: float
    duration: float

class Segments(BaseModel):
    segments: List[SegmentBreakdown]
```

---

#### Pass 2: Segment Prompt Generation

**Goal:** For each segment, generate a detailed image generation prompt.

**Prompt:**
```xml
<system>
You are a scene director and cinematographer for a narrative YouTube video.
You are generating image prompts for an AI image generator (Gemini/Flow).

For each segment, read the script line and the character profiles.
Generate a vivid, detailed image generation prompt.

## Input Context

<characters>
{character_profiles}
</characters>

## Output Format

For each segment, output:
- segment_index: int
- script_line: str
- segment_prompt: str
- characters_present: List[str] (e.g., ["@Alice", "@Bob"])

## Rules for segment_prompt

1. **Opening style anchor:** Every prompt must start with style descriptors that match the video's visual identity.
   - Example: "Cinematic wide shot, photorealistic 3D render, Secret Level / Love Death and Robots style, highly detailed, cinematic lighting, volumetric fog."

2. **Scene description:** Describe the setting, lighting, atmosphere, and mood.
   - Include specific lighting: golden hour, twilight, harsh midday, moonlight, candlelight, etc.
   - Include atmosphere: fog, mist, rain, dust, snow, heat shimmer.
   - Use shot selection based on the content:
     - Landscapes / establishing scenes → wide shot or extreme wide shot
     - Emotional character moments → close-up or medium shot
     - Action / movement → medium shot or over-the-shoulder
     - Objects / details → close-up or extreme close-up

3. **Character placement:** If characters are present, describe their:
   - Position in the frame (center, foreground, background, left-third)
   - Action / pose (walking, sitting, looking away, mid-stride, reaching out)
   - Expression (worried, determined, joyful, terrified)
   - Clothing reference (use the character's description from the profile)
   - Do NOT copy the full character profile — describe them concisely in the scene context.

4. **Camera and framing:**
   - Shot type: extreme wide shot, wide shot, medium shot, close-up, extreme close-up, over-the-shoulder, Dutch angle, bird's eye view, worm's eye view.
   - Lens feel: shallow depth of field, deep focus, telephoto compression, wide-angle distortion.
   - Movement implication: static, tracking, handheld, dolly-in.
   - Note: Since the final image is static (with motion effects applied later), describe the image as a key frame from the chosen camera position.

5. **Color palette and grading:**
   - Describe the dominant color palette: warm desaturated, cool blue-teal, high-contrast noir, vibrant saturated, muted earth tones.
   - Mention lighting color temperature if relevant.

6. **Negative constraints:** End with "no text, no watermark, no logo, no UI elements."

7. **Length:** Keep prompts to 3–6 lines, comma-separated. Rich detail but not a novel.

8. **Character references:**
   - If a character is visually present in the segment, include their name in characters_present as @Name.
   - If a character is mentioned but not shown (e.g., "Alice thought about Bob"), do NOT include @Bob unless Bob is visible in the scene.

9. **Consistency:**
   - Maintain visual consistency across segments. If Segment 1 is "dark forest at twilight," Segment 2 in the same forest should not suddenly be "bright sunny meadow" unless the script explicitly describes a time/location change.

## Example Good Prompt

script_line: "Alice walked through the dark forest, her heart pounding."
segment_prompt: "Cinematic wide shot, photorealistic 3D render, Secret Level / Love Death and Robots style, highly detailed, cinematic lighting. A dark enchanted forest at twilight, ancient gnarled trees with twisted branches, dense fog rolling between the trunks, faint golden moonlight filtering through the canopy. Alice in the foreground, center-left, walking cautiously on a moss-covered path, her red wool coat visible, determined yet worried expression, arms slightly out for balance. Shallow depth of field, background trees blurred into dark silhouettes. Cool blue-green palette with warm highlights from moonlight. Atmospheric, tense, mysterious. no text, no watermark, no logo."

## Example Bad Prompt

script_line: "Alice walked through the dark forest, her heart pounding."
segment_prompt: "A forest. Alice walking. Trees."  ❌ TOO VAGUE

segment_prompt: "Anime style, cel-shaded, chibi character, Alice in a forest, kawaii, sparkles, bright pastel colors."  ❌ WRONG STYLE

segment_prompt: "A dark forest at twilight. Ancient gnarled trees with twisted branches. Dense fog rolling between the trunks. Faint golden moonlight filtering through the canopy. Alice in the foreground, center-left, walking cautiously on a moss-covered path. Her red wool coat visible. Determined yet worried expression. Arms slightly out for balance. Shallow depth of field. Background trees blurred into dark silhouettes. Cool blue-green palette with warm highlights from moonlight. Atmospheric, tense, mysterious. No text, no watermark, no logo."  ❌ TOO LONG AND SENTENCE-BASED

## Character Profile Usage

You are provided with the character list (name, description, front_profile_prompt, turnaround_prompt).
When a character appears in a segment:
1. Extract their key visual traits from the description (hair, clothing, build, expression)
2. Describe them briefly in the scene context (e.g., "Alice in her red wool coat, determined expression")
3. Do NOT paste the full profile prompt into the segment prompt
4. Tag them in characters_present as @Name

Return ONLY a JSON object with a "segments" array.
</system>

<segments>
{segment_list_from_pass_1}
</segments>

<characters>
{character_profiles}
</characters>
```

**Output schema:**
```python
class SegmentPrompt(BaseModel):
    segment_index: int
    script_line: str
    segment_prompt: str
    characters_present: List[str]  # ["@Alice"]
    start_time: float
    end_time: float
    duration: float

class SegmentPrompts(BaseModel):
    segments: List[SegmentPrompt]
```

### 5.4 Character References in Prompts

**Recommendation:** Concise prompt + metadata tags.

- The **segment prompt** contains a brief visual description of the character (e.g., "Alice in her red coat, looking worried")
- The **characters present** are tagged as metadata: `["@Alice"]`
- The **full character profile** is stored separately in `characters.json`
- When the user generates the image, they can combine the segment prompt + the full profile if needed

**Example segment prompt:**
```
Cinematic wide shot, a dark forest at twilight, dense trees with golden rays
filtering through the canopy. Alice in her red coat, looking worried,
standing on a mossy path. Misty atmosphere, warm desaturated colors.
```

**Metadata:**
```json
{
  "characters_present": ["@Alice"],
  "script_line": "Alice walked through the dark forest, her heart pounding.",
  "start_time": 0.0,
  "end_time": 5.0
}
```

### 5.5.1 API Call Strategy

**Primary approach:** Send all segments in **one single API call**.

Rationale:
- A 15-minute video with ~250 segments fits comfortably within Kimi K2.6 Turbo's ~200K token context window
- Estimated usage: ~24K tokens total (~12% of context window)
- One call ensures **perfect continuity** across all segments — the AI can see the full narrative arc and maintain consistent lighting, color palette, and atmosphere
- No risk of batch boundary artifacts where segment 25 and 26 have different styles

**Fallback approach:** If a single call fails (e.g., token limit on extremely long videos, or timeout), use **overlapping batches**:
- Batch size: 25 segments
- Overlap: 5 segments (last 5 of previous batch included as "already generated context")
- Example: Batch 1 = segments 1–25, Batch 2 = segments 21–50, Batch 3 = segments 46–75, etc.
- This gives the AI trailing context for continuity while keeping each call under token limits

**Backend implementation:**
```python
async def generate_segment_prompts(segments, characters):
    # Try single call first
    try:
        result = await call_fireworks_all_segments(segments, characters)
        return result
    except TokenLimitError:
        # Fallback to overlapping batches
        return await generate_in_overlapping_batches(segments, characters, batch_size=25, overlap=5)
```

### 5.5 Output Schema

```python
class SegmentPrompt(BaseModel):
    segment_index: int
    script_line: str
    segment_prompt: str
    characters_present: List[str]  # ["@Alice"]
    start_time: float
    end_time: float
    duration: float  # computed

class SegmentPrompts(BaseModel):
    segments: List[SegmentPrompt]
```

### 5.6 UI Presentation

- **Table view:**
  - Segment #
  - Script line
  - Start → End time
  - Segment prompt
  - Characters present
- **Editable:** User can edit segment prompts before proceeding
- **Split/Merge:** User can manually split or merge segments

### 5.7 Output

| File | Description |
|------|-------------|
| `segments.json` | All segment prompts with timing and metadata |

---

## 6. Step 4: Image Uploading

### 6.1 Input Requirements

| Property | Value |
|----------|-------|
| **Format** | PNG only |
| **Resolution** | 1920×1080 (minimum) |
| **Aspect ratio** | 16:9 |
| **Validation** | Reject non-16:9 images. Warn if < 1920×1080. |

### 6.2 UI: Grid View

- Grid of all segments from `segments.json`
- Each segment cell shows:
  - Segment number
  - Thumbnail (if uploaded, else placeholder)
  - **"Upload" button** — click to upload one image for this segment
  - **"Details" button** — shows script line, segment prompt, characters, timing
- Images are uploaded **one by one** per segment. No bulk upload.
- User can click through the grid systematically to upload each scene.

### 6.3 Details Panel

When "Details" is clicked:
- Script line
- Segment prompt
- Characters present (with links to their profiles)
- Start time → End time
- Duration

### 6.4 Placeholder

- If no image is uploaded, show a grey placeholder with the segment number
- User can still proceed to Step 5, but the placeholder will be rendered as a black/gray slide in the final video

### 6.5 Image Storage

- Store images as `{segment_index:04d}.png`
- Also store the generation prompt in `segments.json` (already present)
- Optional: store which AI model generated the image (user inputs this)

### 6.6 Output

| File | Description |
|------|-------------|
| `images/0001.png` | Uploaded image for segment 1 |
| `images/0002.png` | Uploaded image for segment 2 |
| ... | ... |

---

## 7. Step 5: Video Generation

### 7.1 Motion Effects

**Available effects (checkboxes per segment):**

| Effect | ffmpeg Filter | Description |
|--------|---------------|-------------|
| **Pan left** | `zoompan` + `x` expression | Slow pan left-to-right |
| **Pan right** | `zoompan` + `x` expression | Slow pan right-to-left |
| **Pan up** | `zoompan` + `y` expression | Slow pan bottom-to-top |
| **Pan down** | `zoompan` + `y` expression | Slow pan top-to-bottom |
| **Zoom in** | `zoompan` + `z` expression | Slow zoom in (3-5% total) |
| **Zoom out** | `zoompan` + `z` expression | Slow zoom out (3-5% total) |

**NOT included:** Ken Burns (combo zoom + pan) — user explicitly excluded this.

**Rules:**
- **One effect per segment** (user selects from dropdown or checkbox)
- **Default:** No effect (static image)
- **Effect parameters:**
  - Zoom range: 3-5% total over segment duration
  - Pan speed: slow and smooth, adjustable via `on/total_frames` multiplier

### 7.2 Transition Between Segments

- **Hard cut only** (no crossfade, no fade to black)
- Instant switch at the segment boundary

### 7.3 Caption Burning (Optional)

Captions are **not burned by default**. The user can choose to burn captions into the final video or add them manually in an external video editor.

**UI Option:**
- Checkbox: `[ ] Burn captions into final video` (unchecked by default)
- If checked, the SRT captions are hardcoded into the output MP4

**If burned:**

| Property | Value |
|----------|-------|
| **Font** | Arial |
| **Size** | 22pt |
| **Color** | White |
| **Outline** | Black outline |
| **Display style** | Full line display (not word-by-word karaoke) |
| **Position** | Bottom center |
| **Background** | None (outline handles contrast) |

**Implementation:**
- Convert `captions.srt` to `captions.ass` with custom style
- Style definition in ASS:
  ```
  Style: Default,Arial,22,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,0
  ```
  - Font: Arial, 22pt
  - Primary color: White (`&H00FFFFFF`)
  - Outline color: Black (`&H00000000`)
  - Outline width: 2px
  - Alignment: 2 (bottom center)
- Burn with ffmpeg: `-vf "subtitles=captions.ass:original_size=1920x1080"`

### 7.4 No Background Music

- No music track
- Voiceover is the only audio

### 7.5 Video Pipeline (ffmpeg)

**Per segment:**
1. Load image `images/{segment_index:04d}.png`
2. Calculate duration: `end_time - start_time`
3. Calculate total frames: `int(duration * 24)`
4. If effect selected:
   - Apply `zoompan` with appropriate expression
   - Example (zoom in):
     ```
     zoompan=z='1+on/{total_frames}*0.03':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps=24
     ```
5. If no effect:
   - Loop image for duration
6. Scale and pad to 1920×1080:
   ```
   scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black
   ```
7. Encode to short MP4:
   ```bash
   ffmpeg -y -loop 1 -i {image}.png -filter_complex "..." -t {duration} -c:v libx264 -r 24 -pix_fmt yuv420p -crf 23 -preset fast {segment_clip}.mp4
   ```

**Assembly (without captions):**
1. Create `concat.txt` (ffconcat format):
   ```
   ffconcat version 1.0
   file 0001_segment.mp4
   file 0002_segment.mp4
   ...
   ```
2. Concatenate all segments:
   ```bash
   ffmpeg -y -f concat -safe 0 -i concat.txt -c copy temp_video.mp4
   ```
3. Mix in voiceover audio:
   ```bash
   ffmpeg -y -i temp_video.mp4 -i voiceover.mp3 -c:v copy -c:a aac -b:a 192k -shortest output.mp4
   ```

**Assembly (with captions burned):**
After step 3 (audio mix), add:
```bash
ffmpeg -y -i temp_video.mp4 -vf "subtitles=captions.ass:original_size=1920x1080" -c:v libx264 -crf 23 -preset fast -c:a copy output.mp4
```

**Final output specs:**
- Resolution: 1920×1080
- Frame rate: 24 fps
- Codec: H.264 (libx264)
- Pixel format: yuv420p
- Container: MP4
- Audio: AAC, 192 kbps

### 7.6 UI

- **Effect selection:** Auto-assigned by default. Each segment gets a randomly chosen motion effect from the pool (pan left/right/up/down, zoom in/out). No two adjacent segments are guaranteed to have the same effect.
- **Effect override:** User can click any segment to override its auto-assigned effect via dropdown.
- **Burn captions checkbox:** `[ ] Burn captions into final video` (unchecked by default)
- **Download SRT button:** Optional. User can download `captions.srt` before generating video, for use in external video editors.
- **Generate Video button:** Triggers ffmpeg pipeline
- **Progress bar:** Shows current segment being processed
- **Download Video button:** Appears when complete. Downloads `output.mp4`.

---

## 8. Data Model & Project State

### 8.1 Project Structure

```
project/
├── voiceover.mp3                    # Primary input
├── original_script.md              # Optional user input
├── words.json                      # Whisper word-level output
├── transcript_raw.txt              # Raw Whisper transcript
├── source_of_truth_script.txt      # AI-corrected final script
├── characters.json                 # Step 2 output
├── segments.json                   # Step 3 output
├── captions.srt                    # Generated SRT
├── captions.ass                    # Styled ASS for burning (optional)
├── images/
│   ├── 0001.png
│   ├── 0002.png
│   └── ...
├── output/
│   └── output.mp4                  # Final video
└── .conduit/                       # Internal metadata
    ├── project.json
    └── state.json
```

### 8.2 Key JSON Schemas

**`characters.json` (after Step 2 Call 1 — extraction):**
```json
{
  "characters": [
    {
      "name": "Alice",
      "type": "speaking",
      "importance": "major",
      "description": "Young woman, 20s, human, long auburn hair loose, fair skin, slender build, green eyes, almond shape, determined expression, oval face, slight frown, wearing a red wool coat over a dark turtleneck, leather boots"
    }
  ]
}
```

**`characters.json` (after Step 2 Call 2 — prompt generation):**
```json
{
  "characters": [
    {
      "name": "Alice",
      "type": "speaking",
      "importance": "major",
      "description": "Young woman, 20s, human, long auburn hair loose, fair skin, slender build, green eyes, almond shape, determined expression, oval face, slight frown, wearing a red wool coat over a dark turtleneck, leather boots",
      "front_profile_prompt": "Secret Level / Love Death and Robots style animation, photorealistic 3D render, cinematic lighting, subsurface skin scattering, physically based rendering, hyper-detailed face, face depth, realistic eyes, volumetric lighting, sharp detailed textures, clean render, young woman, 20s, human, long auburn hair loose, fair skin, slender build, green eyes, almond shape, determined expression, oval face, slight frown, wearing a red wool coat over a dark turtleneck, leather boots, medium shot, upper body and face, dark forest background, soft golden light, no text, no watermark, no logo",
      "turnaround_prompt": "Secret Level / Love Death and Robots style animation, photorealistic 3D render, character turnaround reference sheet, professional character modeling sheet, cinematic lighting, subsurface skin scattering, physically based rendering, hyper-detailed face, face depth, realistic eyes, sharp detailed textures, clean render, pure white background, landscape composition, no text, no watermark, no logo, young woman, 20s, human, long auburn hair loose, fair skin, slender build, green eyes, almond shape, determined expression, oval face, slight frown, wearing a red wool coat over a dark turtleneck, leather boots, three-view turnaround, front and left-side profile and back, identical proportions, natural standing pose, arms at sides, eye-level camera, upper-right shows six head angles, front-facing and slight downward and back of head and left-side profile and near-side comparison and 3/4 profile, lower-right shows six close-up detail shots, upper garment texture and lower body clothing and hip detail and leg texture and eyes and facial features and full shoe close-up, strict character consistency, no cropping, no extra props, no text, no logo, no watermark"
    }
  ]
}
```

**`segments.json`:**
```json
{
  "segments": [
    {
      "segment_index": 1,
      "script_line": "Alice walked through the dark forest.",
      "segment_prompt": "Cinematic wide shot, a dark forest at twilight, dense trees with golden rays filtering through the canopy. Alice in her red coat, looking worried, standing on a mossy path. Misty atmosphere, warm desaturated colors.",
      "characters_present": ["@Alice"],
      "start_time": 0.0,
      "end_time": 5.0,
      "duration": 5.0,
      "image_path": "images/0001.png",
      "effect": "zoom_in"
    }
  ]
}
```

**`project.json` (metadata):**
```json
{
  "project_name": "Conduit",
  "created_at": "2026-06-02T12:00:00Z",
  "last_modified": "2026-06-02T12:00:00Z",
  "steps_completed": ["step_1", "step_2"],
  "voiceover_format": "mp3",
  "whisper_model": "whisper-1",
  "llm_provider": "fireworks",
  "llm_model": "accounts/fireworks/routers/kimi-k2p6-turbo"
}
```

---

## 9. Tech Stack

### 9.1 Backend

| Component | Technology | Version |
|-----------|------------|---------|
| **Framework** | FastAPI | 0.115+ |
| **Python** | CPython | 3.12+ |
| **Runtime** | Uvicorn | standard |
| **API client** | OpenAI SDK | 1.60+ |
| **Audio processing** | pydub | 0.25.1 |
| **SRT handling** | srt | 3.5.3 |
| **ASS handling** | pysubs2 | 1.8.1 (optional) |
| **Video engine** | ffmpeg | 8.x+ (verified: 8.1.1) |
| **Data validation** | Pydantic | 2.x |
| **Project storage** | SQLite + JSON files | — |

### 9.2 Frontend

| Component | Technology | Notes |
|-----------|------------|-------|
| **Framework** | React (Vite) | Familiar ecosystem, shadcn/ui available |
| **Styling** | Tailwind CSS | Utility-first, rapid prototyping |
| **UI Components** | shadcn/ui | DataTable, Card, Dialog, Tabs, Checkbox |
| **Build tool** | Vite | Fast HMR, modern bundling |
| **File upload** | Native HTML5 + drag-and-drop | Simple grid |
| **State** | Server-side (SQLite) | No complex client state needed |
| **Type safety** | TypeScript `strict` mode | Enabled in `tsconfig.json` (zero errors) |

### 9.3 Infrastructure

| Component | Technology | Notes |
|-----------|------------|-------|
| **Hosting** | Local (localhost) | FastAPI on Uvicorn, single user |
| **Database** | SQLite (file-based) | Sufficient for single-user |
| **File storage** | Local filesystem | `./projects/` directory |
| **Secrets** | `.env` file or env vars | API keys |
| **GPU** | RTX 3060M (optional) | Not needed for ffmpeg; used for local AI if needed |

---

## 10. Deployment

### 10.1 Local Deployment

**Target:** User's laptop (RTX 3060M, Windows)

**Prerequisites:**
1. Python 3.12+ installed
2. ffmpeg installed and on PATH
3. Git (optional, for cloning)

**Setup:**
```bash
# Clone or unzip project
# Create venv
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or create .env file)
set OPENAI_API_KEY=sk-...
set FIREWORKS_API_KEY=...

# Run
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Access:**
- Open browser to `http://localhost:8000`
- No auth needed (single user, local only)

**Project Storage:**
- All projects stored in `./projects/` directory (relative to app root)
- SQLite database at `./projects/conduit.db`
- Each project gets a UUID subfolder: `./projects/{uuid}/`

**Process:**
- Single FastAPI process (Uvicorn with 1 worker)
- Video generation runs synchronously in the request (since it's local, no timeout for ffmpeg itself)
- AI API calls (Whisper, Fireworks) have explicit timeouts: `timeout=60.0` on OpenAI client, `asyncio.timeout(120)` on Fireworks completions
- ffmpeg is CPU-bound; no GPU needed for video encoding (RTX 3060M is idle during video generation)

### 10.2 No Railway / Cloud Deployment

This tool is designed for local use only. If future cloud deployment is needed, the following would need to be added:
- Railway Volume (or S3) for persistent storage
- Background task queue (Celery / Redis) for video generation
- Auth system (password or OAuth)
- These are **not in scope** for the current design.

---

## 11. Security

| Concern | Mitigation |
|---------|------------|
| **API keys** | Stored in `.env` file or local env vars, never in code |
| **File uploads** | Validate MIME type, size, resolution. No executable uploads. |
| **Project isolation** | Each project gets a UUID subfolder. No path traversal. |
| **Not open source** | Repo is private. No hardcoded secrets. |
| **Future open source** | All secrets are env-var based. Configurable via `.env` file. |
| **Local access** | localhost only — no public exposure |
| **Exception handler leaks** | Global exception handler returns generic error message to client; full exception logged server-side via `logging` module (never return `str(exc)` to client) |
| **Command injection (ffmpeg)** | All ffmpeg commands passed as lists to `subprocess.run` with `shell=False` (default). No shell string concatenation. `shlex.quote()` is not needed for list-based commands. |

---

## 12. Error Handling

| Scenario | Behavior |
|----------|----------|
| **Whisper API failure** | Auto-retry 3× with exponential backoff (1s, 2s, 4s). If all fail, show error message + "Retry" button. |
| **Fireworks AI failure (Step 1 cross-reference)** | Show partial results (if any) + "Retry" button. Save any approved changes before retry. |
| **Fireworks AI failure (Step 2 character extraction)** | Show error + "Retry" button. If Call 1 succeeded but Call 2 failed, preserve the character list and retry Call 2 only. |
| **Fireworks AI failure (Step 3 segment breakdown)** | Show error + "Retry" button. No partial state to save yet. |
| **Fireworks AI failure (Step 3 prompt generation)** | If using single call: show error + "Retry" button. If using overlapping batches: show completed batches, retry failed batch only. |
| **ffmpeg failure** | Show friendly error message (e.g., "Video generation failed on segment 47. Check image file.") + option to view raw ffmpeg stderr. Allow retry. |
| **Image upload failure** | Inline validation error. Auto-convert RGBA → RGB. Auto-resize with warning if dimensions are off. |
| **Missing images** | Block Step 5. Show warning: "Upload images for all segments before generating. N segments missing." |
| **Network timeout** | Auto-retry 3× with backoff. If persistent, show "Check your connection" message. |

**Key principle:** Save project state after every successful step. If a step fails, the user can fix the issue and retry from that point without losing previous work.

---

## 13. Open Questions

These are explicitly deferred and not blockers for the spec:

| # | Question | Context | Status |
|---|----------|---------|--------|
| 1 | **Gemini/Flow prompt format specifics** | Step 2: Prompt format resolved — embedded in system prompt. | Resolved |
| 2 | **AI smart segment break logic** | Step 3: Exactly how the AI decides to split long sentences. | Deferred — will be refined in prompt engineering |
| 3 | **Frontend framework choice** | React vs Svelte. | Resolved — React + Vite + shadcn/ui + Tailwind |
| 4 | **Batch vs single-call for segments** | Step 3: One API call per segment or batch all segments? | Resolved — Single call primary, overlapping batch fallback if token limit exceeded |
| 5 | **Error handling UX** | What happens when Whisper API fails, or Fireworks API times out? | Resolved — Auto-retry 3× with backoff, partial results saved after each step, user can retry from failed step |
| 6 | **Image upload concurrency** | Can user upload multiple images at once? | Resolved — One by one, grid view with Details button per segment |
| 7 | **UI navigation pattern** | Wizard vs tabs vs sidebar? | Resolved — Wizard with Next/Back buttons |
| 8 | **Motion effects scope** | One global random effect or per-segment random? | Resolved — Per-segment random, user can override individual segments |
| 9 | **Step 2 skip option** | Can user skip character extraction? | Resolved — Always mandatory (all stories have characters) |
| 10 | **Cascade on Back** | What happens when user edits upstream step? | Resolved — Auto-invalidate all downstream steps |
| 11 | **Scene image style** | Same as characters or different? | Resolved — Same Secret Level / LDR style for visual consistency |
| 12 | **SRT download** | Can user download SRT without generating video? | Resolved — Yes, download SRT button available at Step 5 |
| 13 | **Video preview before export** | Can user preview a single segment before generating full video? | Deferred — nice-to-have |
| 14 | **Project management** | Can user have multiple projects? | Deferred — assumed yes, but not designed |

---

## Appendix A: Effect ffmpeg Expressions

| Effect | Expression |
|--------|-----------|
| **Zoom in** | `zoompan=z='1+on/{total_frames}*0.03':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps=24` |
| **Zoom out** | `zoompan=z='1+on/{total_frames}*0.03':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps=24` (with `z` decreasing) |
| **Pan left** | `zoompan=z=1:x='iw/2-(iw/zoom/2)+on*2':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps=24` |
| **Pan right** | `zoompan=z=1:x='iw/2-(iw/zoom/2)-on*2':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps=24` |
| **Pan up** | `zoompan=z=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+on*2':d={total_frames}:s=1920x1080:fps=24` |
| **Pan down** | `zoompan=z=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-on*2':d={total_frames}:s=1920x1080:fps=24` |

---

## Appendix B: Prompt Templates

### B.1 Cross-Reference Step 1a (Identify Differences)

```
You are a transcript editor. You will compare a voiceover transcript against
an original script and identify all differences.

The <original_script> is the canonical ground truth.
The <voiceover_transcript> is what the speaker actually said.

Your task:
1. Read both texts carefully.
2. Identify every difference: transcription errors, filler words, omissions, paraphrasing.
3. For each difference, classify it:
   - "correction": Whisper misheard a word (e.g., "there" instead of "their")
   - "omission": A word from the script was not spoken
   - "addition": A word was spoken but not in the script (including filler words)
   - "filler_removed": A filler word ("um", "uh", "like", "you know") was spoken

For each difference, output:
- transcript_text: the exact text from the voiceover
- script_text: the corresponding text from the original script
- corrected_text: the final chosen text (prefer the script unless the ad-lib is clearly better)
- reason: brief explanation
- confidence: 0.0 to 1.0

Return ONLY a JSON object with a "changes" array.
```

### B.2 Cross-Reference Step 1c (Generate Source of Truth)

```
You are a transcript editor. Given the following approved changes, produce a
clean "source of truth" script.

Apply all approved changes to the original script.
Remove all filler words that were marked as "filler_removed".
Preserve the tone and style of the original script.
Do not add content that was not in either the script or the transcript.

Return ONLY the corrected text as a plain string.
```

### B.3 Character Extraction — Call 1 (Character List)

```
You are a character extraction engine. Read the script and identify all
entities that are visually important in the story.

Extract:
1. Named speaking characters (e.g., "Alice", "Bob")
2. Significant NPCs or creatures that appear visually (e.g., "the dragon", "the old merchant")
3. Any NPC entity that has a visual presence

For each entity, output:
- name: the canonical name
- type: "speaking" | "creature" | "npc_entity"
- importance: "major" if the entity appears in multiple scenes or is central to the plot. "minor" if they appear once or are background.
- description: a detailed visual description of the character's appearance, clothing, and expression. If the script does not describe them in detail, infer a visually interesting design that fits the narrative. Do NOT leave fields blank.

Return ONLY a JSON object with a "characters" array.
```

### B.3 Character Extraction — Call 2 (Prompt Generation)

```
You are a character art prompt writer for an animated series in the visual style of Secret Level and Love Death and Robots.

For each character in the list, generate TWO prompts:

Prompt A — Front Profile:
Style anchors (always include):
Secret Level / Love Death and Robots style animation, photorealistic 3D render, cinematic lighting, subsurface skin scattering, physically based rendering, hyper-detailed face, face depth, realistic eyes, volumetric lighting, sharp detailed textures, clean render
Then append in this order:
Age, gender, race or species type
Hair description (length, style, color, texture)
Skin tone and build
Eye description (color, shape, expression)
Face shape and expression
Outfit or upper body description
Lower body or full body description if non-humanoid
Shot type and framing
Background
no text, no watermark, no logo
Rules:
Keep prompts to 2-4 lines maximum, comma-separated, no full sentences
Never use anime or cel-shading language
For hybrid or monster characters, describe the non-human parts with precise anatomical and material detail
Always end with background description and no text

Prompt B — Turnaround Reference Sheet:
Always open with:
Secret Level / Love Death and Robots style animation, photorealistic 3D render, character turnaround reference sheet, professional character modeling sheet, cinematic lighting, subsurface skin scattering, physically based rendering, hyper-detailed face, face depth, realistic eyes, sharp detailed textures, clean render, pure white background, landscape composition, no text, no watermark, no logo
Then append in this order:
Age, gender, race or species type
Hair description (length, style, color, texture)
Skin tone and build
Eye description (color, shape, expression)
Face shape and expression
Outfit or upper body description
Lower body or full body if non-humanoid
Three-view turnaround instruction: left side of composition shows three full-body views — front, left-side profile, and back — same character, identical proportions, natural standing pose, arms at sides, eye-level camera
Upper-right instruction: upper-right section shows six head-angle references — front-facing, slight downward, back of head, left-side profile, near-side comparison, 3/4 profile
Lower-right instruction: lower-right section shows six close-up detail shots — upper garment texture, lower body clothing, hip detail, leg or skin texture, eyes and facial features, full shoe close-up
strict character consistency throughout, no cropping, no extra props, no text, no logo, no watermark
Rules:
Keep the character description portion to 2-4 lines, comma-separated, no full sentences
Never use anime or cel-shading language
For non-humanoid or hybrid characters, replace shoe/clothing detail shots with anatomically appropriate equivalents
All three turnaround views and all detail shots must depict the exact same character
Always end with the consistency and no text line

Important rules:
- For minor characters with minimal description, keep the prompt shorter but still fully specified.
- For major characters, provide more detailed prompts.
- Do NOT leave fields blank.

For each character, output:
- name: the canonical name
- front_profile_prompt: the single image prompt (Prompt A)
- turnaround_prompt: the reference sheet prompt (Prompt B)

Return ONLY a JSON object with a "characters" array.
```

### B.4 Segment Prompt Generation (Step 3 — Pass 2)

```
You are a scene director and cinematographer for a narrative YouTube video.
You are generating image prompts for an AI image generator (Gemini/Flow).

For each segment, read the script line and the character profiles.
Generate a vivid, detailed image generation prompt.

## Input Context

<characters>
{character_profiles}
</characters>

## Output Format

For each segment, output:
- segment_index: int
- script_line: str
- segment_prompt: str
- characters_present: List[str] (e.g., ["@Alice", "@Bob"])

## Rules for segment_prompt

1. Opening style anchor: Every prompt must start with style descriptors.
   Example: "Cinematic wide shot, photorealistic 3D render, Secret Level / Love Death and Robots style, highly detailed, cinematic lighting, volumetric fog."

2. Scene description: Describe the setting, lighting, atmosphere, and mood.
   - Include specific lighting: golden hour, twilight, harsh midday, moonlight, candlelight.
   - Include atmosphere: fog, mist, rain, dust, snow, heat shimmer.
   - Shot selection: landscapes → wide shot, emotional moments → close-up, action → medium shot.

3. Character placement: If characters are present, describe their position, action, pose, expression, and clothing.
   - Do NOT copy the full character profile — describe them concisely in the scene context.

4. Camera and framing: Shot type, lens feel, movement implication.
   - Note: The image is a static key frame (motion effects are applied later).

5. Color palette and grading: Describe the dominant color palette and lighting temperature.

6. Negative constraints: End with "no text, no watermark, no logo, no UI elements."

7. Length: Keep prompts to 3–6 lines, comma-separated.

8. Character references: If a character is visually present, include @Name in characters_present.
   If mentioned but not shown, do NOT include them.

9. Consistency: Maintain visual consistency across segments. If Segment 1 is "dark forest at twilight,"
   Segment 2 in the same forest should not suddenly be "bright sunny meadow" unless the script explicitly describes a change.

## Character Profile Usage

When a character appears in a segment:
1. Extract their key visual traits from the description (hair, clothing, build, expression)
2. Describe them briefly in the scene context (e.g., "Alice in her red wool coat, determined expression")
3. Do NOT paste the full profile prompt into the segment prompt
4. Tag them in characters_present as @Name

Return ONLY a JSON object with a "segments" array.
```

---

## 14. Frontend Design

### 14.1 Aesthetic Direction

**Dark & Cinematic.** The interface evokes a film editing suite — moody, focused, and professional. The aesthetic aligns with the "Secret Level / Love Death and Robots" visual identity of the generated content.

### 14.2 Theme

**Dark mode only.** No light mode toggle. The user will spend hours editing prompts and uploading images; a dark background reduces eye strain and keeps focus on the content.

### 14.3 Typography

| Role | Font | Usage |
|------|------|-------|
| **Display / Logo** | Playfair Display | App title, step headings, major labels |
| **Body / UI text** | Source Sans 3 | Paragraphs, descriptions, form labels |
| **Monospace / Technical** | JetBrains Mono | JSON views, code blocks, timestamps, segment indices |

**Font loading:** Google Fonts CDN or self-hosted via `@fontsource` packages.

### 14.4 Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-base` | `#0a0a0f` | Page background |
| `--bg-surface` | `#1a1a2e` | Cards, panels, sidebar |
| `--bg-elevated` | `#252540` | Hover states, dropdowns, modals |
| `--accent-primary` | `#f0a040` | Buttons, active states, progress indicators, logo |
| `--accent-secondary` | `#2dd4bf` | Links, interactive highlights, secondary actions |
| `--accent-glow` | `rgba(240, 160, 64, 0.15)` | Subtle glow effects behind cards |
| `--text-primary` | `#f0f0f0` | Headings, primary content |
| `--text-secondary` | `#a0a0a0` | Descriptions, metadata, placeholders |
| `--text-muted` | `#6b6b7b` | Disabled states, borders |
| `--success` | `#22c55e` | Completion indicators |
| `--error` | `#ef4444` | Errors, warnings, missing images |
| `--border` | `rgba(255, 255, 255, 0.08)` | Subtle dividers and card borders |

### 14.5 Layout — Landing Page

The landing page is a **project list dashboard**.

```
┌─────────────────────────────────────────────────────────────┐
│  Conduit                                                    │
│  [+ New Project]                                            │
├─────────────────────────────────────────────────────────────┤
│  My Projects                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Video 1      │  │ Video 2      │  │ Video 3      │      │
│  │ 50% complete │  │ Done         │  │ Not started  │      │
│  │ [Resume]     │  │ [Edit] [×]   │  │ [Start]      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

**Card design:**
- Background: `--bg-surface` with `--border` border
- Hover: subtle `--accent-glow` shadow, border brightens to `--accent-primary` at 30% opacity
- Status badge: colored dot + text (amber = in progress, green = done, gray = not started)
- Delete: small "×" icon on hover

### 14.6 Layout — Wizard (Steps 1–5)

**Horizontal stepper at top**, with generous horizontal margins so content is not edge-to-edge.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   [Step 1] ──→ [Step 2] ──→ [Step 3] ──→ [Step 4] ──→ [Step 5] │
│   Script     Characters   Segments    Images      Video     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    CONTENT AREA                             │
│                 (centered, max-width: 1200px)              │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              [← Back]              [Next →]                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Stepper design:**
- Completed steps: `--accent-primary` checkmark + label
- Current step: `--accent-primary` filled circle + bold label
- Future steps: `--text-muted` empty circle + muted label
- Connector line: `--border` for future, `--accent-primary` for completed

### 14.7 Step 4 — Image Upload Grid

**Uniform grid with large cards.** Each card is a fixed-size thumbnail (e.g., 220px × 160px) with metadata below.

```
┌─────────────────────────────────────────────────────────────┐
│  Upload Images (187 / 250 uploaded)                         │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────┐ ┌────────────┐ ┌────────────┐             │
│  │  #001      │ │  #002      │ │  #003      │             │
│  │ [thumbnail]│ │ [thumbnail]│ │ [upload]   │             │
│  │ 0:00-0:05  │ │ 0:05-0:10  │ │ 0:10-0:15  │             │
│  │ [Details]  │ │ [Details]  │ │ [Details]  │             │
│  │ Pan Left   │ │ Zoom In    │ │ —          │             │
│  └────────────┘ └────────────┘ └────────────┘             │
│  ...                                                        │
└─────────────────────────────────────────────────────────────┘
```

**Card states:**
- **Uploaded:** Shows thumbnail, segment number, duration, effect badge, "Details" button
- **Missing:** Grey placeholder with segment number, "Upload" button, red border or subtle error tint
- **Hover:** Scale up 1.02, shadow deepens, border brightens

**"Details" button:** Opens a modal or side panel showing:
- Script line
- Segment prompt
- Characters present (with `@Name` tags, clickable to view full profile)
- Start time → End time
- Duration

### 14.8 Step 5 — Video Generation

```
┌─────────────────────────────────────────────────────────────┐
│  Generate Video                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [✓] 250 images uploaded                                    │
│  [✓] 250 effects assigned (random)                          │
│                                                             │
│  [ ] Burn captions into final video                         │
│                                                             │
│  [Download SRT]  [Generate Video]                           │
│                                                             │
│  ┌─────────────────────────────────────────────┐           │
│  │  Progress: Segment 47 / 250                │           │
│  │  ████████████████████░░░░░░░░░░░░░░░░░░░░ │           │
│  │  18% — Encoding...                          │           │
│  └─────────────────────────────────────────────┘           │
│                                                             │
│  [Download Video] (appears when complete)                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 14.9 Motion & Animation

| Animation | Trigger | Style | Duration |
|-----------|---------|-------|----------|
| **Page transition** | Next / Back click | Fade out (0.2s) → slide in from direction (0.3s) | 0.5s total |
| **Step completion** | AI call succeeds | Card glows `--accent-primary` then settles | 0.6s |
| **Image upload** | File dropped / selected | Border pulses `--accent-primary`, thumbnail fades in | 0.4s |
| **Video generation** | Segment encoded | Progress bar segment fills, counter increments | Per segment |
| **Card hover** | Mouse over grid item | Scale 1.02, shadow deepens, border brightens | 0.2s ease-out |
| **Skeleton loading** | AI call in progress | Shimmer gradient across placeholder blocks | 1.5s loop |
| **Modal open** | Details button clicked | Backdrop fades, modal slides up from bottom | 0.3s |
| **Error shake** | Validation fails | Horizontal shake, red border flash | 0.4s |

### 14.10 Component Design Notes

**Buttons:**
- Primary: `--accent-primary` background, dark text, rounded-lg (8px), hover brightens
- Secondary: `--bg-elevated` background, `--text-primary` text, border `--border`
- Danger: `--error` background, white text

**Inputs:**
- Background: `--bg-surface`
- Border: `--border`, focus: `--accent-primary`
- Text: `--text-primary`
- Placeholder: `--text-muted`

**Cards:**
- Background: `--bg-surface`
- Border: 1px solid `--border`
- Border-radius: 12px
- Shadow: subtle dark shadow (0 4px 6px rgba(0,0,0,0.3))
- Hover: border transitions to `rgba(240, 160, 64, 0.3)`

**Tables:**
- Header: `--bg-elevated` background, uppercase text, `--text-secondary`
- Rows: alternating `--bg-surface` and `--bg-base`
- Hover: `--bg-elevated` highlight
- Border: subtle `--border` between rows

**Modals / Panels:**
- Backdrop: `rgba(0, 0, 0, 0.7)` with blur
- Panel: `--bg-surface`, border-radius 16px, max-width 800px
- Close: top-right "×" icon

### 14.11 Responsive Design

**Desktop only.** Minimum viewport width: 1280px.

This is a creative workstation, not a mobile app. The grid, tables, and side panels are designed for wide screens.

---

*End of Design Specification.*
