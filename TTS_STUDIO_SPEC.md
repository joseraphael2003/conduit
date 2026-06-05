# TTS Studio — Design Specification (Draft)

*A standalone voice generation module for the Conduit platform.*

**Status:** Vision-in-progress. Not complete. Sections marked `[TODO]` are intentionally open for future discussion.

**Relationship to Conduit:** The TTS Studio is a **separate, standalone application module** within the Conduit platform. It does not integrate into the 5-step video pipeline. A user can open the TTS Studio to generate a voiceover from a script, export it as `.mp3`, and later import that `.mp3` into the Video Studio's Step 1 (Script) as a standard voiceover upload.

---

## 1. Core Vision

The TTS Studio is a **local-first, professional voice generation workspace** for YouTube creators who produce narrative content. It produces narrated audio from plain text scripts with a level of control that cloud TTS APIs do not offer: per-segment pacing, consistent character voices, and local, private execution.

**Key Principles:**
- **Standalone:** No dependency on the video pipeline. No shared wizard steps.
- **Local-first:** All synthesis runs on the user's hardware (RTX 3060M). No external TTS APIs.
- **Precision control:** The user can adjust speed, pauses, and emphasis on a per-segment basis, not just globally.
- **Character consistency:** Multi-character dialogue is supported via voice cloning / speaker embedding assignment. Each character gets a consistent voice across the entire script.
- **Project-based:** Work is saved as a "TTS Project" that can be reopened, edited, and re-exported.

---

## 2. High-Level Architecture

### 2.1 Deployment

- **Local only:** Runs on the same FastAPI backend as the Video Studio, but under a separate router namespace (e.g., `/api/v1/tts/`).
- **GPU-bound:** TTS inference uses the RTX 3060M. The backend must detect GPU availability and fail gracefully if CUDA is unavailable.
- **Model storage:** TTS models (base model + speaker embeddings / voice clones) are stored in a local cache directory (e.g., `./models/tts/`). Models are downloaded on first use, not bundled with the app.

### 2.2 Module Separation

```
Conduit Platform
├── Video Studio (existing 5-step wizard)
│   └── /api/v1/projects/
│
└── TTS Studio (new standalone module)
    └── /api/v1/tts/
        ├── /projects          # TTS project CRUD
        ├── /segments          # Segment generation & control
        ├── /voices            # Voice library & cloning
        └── /render            # Export / mixdown
```

**Navigation:** A persistent "Studio Switcher" in the title bar (e.g., dropdown: "Video Studio" / "TTS Studio") switches between the two modules. State is isolated; the Video Studio stepper does not appear in the TTS Studio, and vice versa.

---

## 3. Core Concepts

### 3.1 TTS Project

A self-contained project with:
- **Script text:** The full plain text input.
- **Segments:** Auto-generated or user-defined chunks of the script.
- **Voice mappings:** Which voice (speaker) is assigned to each segment.
- **Per-segment settings:** Speed, pause duration, prosody flags.
- **Generated clips:** Individual `.wav` files per segment, stored in the project directory.
- **Mixdown:** Final exported `.mp3`.

### 3.2 Segments

A **segment** is the atomic unit of control. The script is broken into segments by:
- Paragraph breaks (primary)
- Sentence boundaries (secondary, if paragraphs are too long)
- User manual splits

Each segment is a row in a table/list view and can be:
- Previewed individually
- Regenerated independently
- Assigned a voice
- Given per-segment settings

### 3.3 Voices

A **voice** is a speaker identity that can be used across segments.

**Voice types:**
- **Base voices:** Pre-trained voices that ship with the TTS model (e.g., "male_1", "female_1", "narrator").
- **Cloned voices:** Created by uploading a short audio sample (3–10 seconds) of a voice. The system extracts a speaker embedding and saves it as a reusable voice.
- **Character voices:** Named voices (e.g., "Alice", "Bob") that are either base or cloned voices, assigned to specific characters in the script.

---

## 4. UI Structure

### 4.1 Layout

The TTS Studio uses the same **design system** as the Video Studio (`DESIGN.md` tokens, dark cinematic theme, sharp corners, amber primary action). But the layout is **not a wizard**. It is a **workspace**:

```
┌─────────────────────────────────────────────────────────────┐
│  TITLE BAR                                                  │  48px
│  "Conduit"  |  [TTS Studio ▼]  |  TTS Project Name          │
├─────────────────────────────────────────────────────────────┤
│  TOOL BAR                                                   │  48px
│  [Import Script]  [Add Voice]  [Generate All]  [Export MP3]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  MAIN WORKSPACE (two-pane)                                  │  remaining
│  ┌────────────────────┐  ┌─────────────────────────────┐   │
│  │  SCRIPT PANEL      │  │  SEGMENT LIST / DETAILS     │   │
│  │  (scrollable text  │  │  (table with per-segment    │   │
│  │   area, editable)  │  │   controls, preview btn)    │   │
│  └────────────────────┘  └─────────────────────────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  PREVIEW BAR                                                │  64px
│  [▶ Play Segment]  [⏹ Stop]  Waveform scrubber  [▶ Play All]│
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Key Panels

**Script Panel:**
- Large, editable text area for the full script.
- Plain text only. No Markdown rendering, no formatting toolbar.
- Auto-segmentation runs on import (paragraph → segments).
- Manual segment split: user places cursor and clicks "Split Here" to create a new segment boundary.

**Segment List:**
- Data table with columns (tentative):
  - Segment # (mono-md)
  - Script text (body-md, truncated)
  - Voice (dropdown / badge)
  - Speed (e.g., 0.8x, 1.0x, 1.2x)
  - Duration (mono-md, after generation)
  - Status (badge: pending / generated / error)
  - Actions (ghost "Play", "Regenerate", "Edit" buttons)
- Clicking a row opens a **Detail Panel** (modal or side drawer) with:
  - Full script text for the segment
  - Voice assignment dropdown
  - Speed slider (0.5x – 2.0x)
  - Pause after segment (0s – 5s)
  - Generate / Regenerate button
  - Preview player

**Voice Library:**
- Accessible via "Add Voice" toolbar button.
- Modal showing:
  - Base voices (pre-installed, ready to use)
  - Cloned voices (user-uploaded samples, with play-to-preview)
  - "Clone New Voice" button: upload sample, name it, save embedding

**Preview Bar:**
- Persistent bottom bar (always visible).
- Play / Stop controls.
- Waveform visualization of the currently selected segment (or full mixdown).
- Global "Play All" button (plays segments in sequence with pauses).

---

## 5. Input & Output

### 5.1 Input

| Source | Format | Description |
|--------|--------|-------------|
| **Script import** | `.txt` or `.md` | Plain text. Paragraphs become segments. |
| **Manual entry** | Plain text | Typed directly into the Script Panel. |
| **Voice clone sample** | `.wav` or `.mp3` | 3–10 seconds of clean speech. No background noise. |

### 5.2 Output

| File | Format | Description |
|------|--------|-------------|
| **Segment clips** | `.wav` | Individual renders per segment. 48kHz, 16-bit. |
| **Mixdown** | `.mp3` | Final concatenated audio. 128–192 kbps. |
| **TTS Project** | Directory | Script, segments JSON, voice mappings, settings, clips. |

---

## 6. Key Features (Defined)

### 6.1 Single Narrator Mode (Primary)
- Import a script.
- Auto-segment by paragraph.
- Pick one narrator voice from the Voice Library.
- Generate all segments with global voice.
- Adjust speed and pause per segment if needed.
- Export mixdown.

### 6.2 Multi-Character Dialogue Mode (Secondary)
- Script contains dialogue markers (e.g., `Alice: "Hello there."`, `Bob: "Hi."`).
- System detects markers and auto-assigns segments to characters.
- User maps each character to a voice in the Voice Library.
- Segments are rendered with their assigned character's voice.
- Narration (non-dialogue text) uses the narrator voice.
- **Note:** Dialogue detection and marker format are [TODO].

### 6.3 Per-Segment Control
- **Speed:** 0.5x – 2.0x playback speed. Applied at synthesis time (not resampling).
- **Pause after:** Silence appended after the segment (0s – 5s).
- **Prosody flags:** [TODO] — exact controls (pitch shift, emphasis, breath) depend on TTS model capabilities.
- **Regenerate:** Re-synthesize a single segment without affecting others.

### 6.4 Voice Cloning
- Upload a 3–10 second sample.
- Name the voice (e.g., "My Narrator", "Alice").
- Extract speaker embedding.
- Save to Voice Library (reusable across projects).
- Preview cloned voice before saving.

### 6.5 Project Save / Reopen
- TTS Projects are saved in a dedicated directory (e.g., `./tts-projects/{uuid}/`).
- Contains: `script.txt`, `segments.json`, `settings.json`, `clips/`.
- Reopening restores the full workspace state: script, segments, voice mappings, per-segment settings, and already-generated clips.
- **Note:** Speaker embeddings are stored in a global voice library (shared across all TTS projects), not inside the project directory.

---

## 7. Open Questions & [TODO] Sections

The following sections are **intentionally incomplete** while the vision is refined:

### 7.1 TTS Model Selection `[TODO]`
- Which local TTS model? Options: XTTS v2 (Coqui), Piper, MeloTTS, Zonos, Fish Speech.
- Criteria: voice cloning quality, multi-speaker support, inference speed on RTX 3060M, license, speed control API.
- **Decision needed before implementation.**

### 7.2 Script Parsing & Dialogue Detection `[TODO]`
- Format for dialogue markers in plain text? `Character: "Dialogue"`? `[@Character] Dialogue`? Custom syntax?
- How to distinguish narration from dialogue?
- Should the user manually tag characters, or should AI auto-detect?
- **Decision needed before UI design.**

### 7.3 Prosody Control Granularity `[TODO]`
- What controls are actually possible with the chosen TTS model?
- Pitch shift? Emphasis on specific words? Breath insertion? SSML support?
- If the model supports only global speed, the per-segment UI must be simplified.
- **Decision needed after model selection.**

### 7.4 Audio Mixing & Transitions `[TODO]`
- Cross-fades between segments? Or hard cuts + silence?
- Normalization across segments (loudness)?
- How to handle segments with different voices butting against each other?
- **Decision needed before render pipeline design.**

### 7.5 Integration with Video Studio `[TODO]`
- Should TTS projects appear in the Video Studio project list? Or are they completely separate?
- One-click "Send to Video Studio" that exports `.mp3` and auto-creates a Video Project with the same script?
- Or manual export/import only?
- **Decision needed before navigation design.**

### 7.6 UI Workflows `[TODO]`
- Exact segment list columns and interaction patterns.
- Detail panel: modal vs. side drawer vs. inline expand.
- Waveform visualization: is it a full waveform or a simple progress bar?
- Global settings: are there project-level defaults (default voice, default speed) that per-segment settings inherit?
- **Decision needed after core features are locked.**

### 7.7 Backend Schema `[TODO]`
- Database tables / JSON files for TTS projects, segments, voice mappings.
- File storage structure for clips and embeddings.
- API endpoints (not yet defined).
- **Decision needed after UI workflows are defined.**

### 7.8 Error Handling & Edge Cases `[TODO]`
- What happens if a segment fails to synthesize (OOM, bad text, model error)?
- Maximum script length? Maximum segment length?
- GPU out-of-memory handling during inference.
- **Decision needed after model selection.**

---

## 8. Non-Goals (Explicitly Out of Scope)

To prevent scope creep while the vision is forming, the following are **not part of the TTS Studio**:

- **Real-time / streaming TTS:** All generation is batch (offline) rendering.
- **Music or SFX generation:** TTS only. No background music, no sound effects.
- **Timeline / DAW interface:** No multi-track timeline, no audio clips dragged on a grid. The segment list is a table, not a DAW.
- **Cloud sync:** All local, no remote storage or sharing.
- **Video preview:** The TTS Studio does not show images or video. Audio only.
- **SSML input:** Unless the chosen TTS model natively requires it, plain text is the only input format.
- **Voice marketplace:** No downloading voices from the internet. Only base model voices + user-cloned voices.

---

## 9. Tech Stack (Tentative)

Assumes the same backend/frontend as the Video Studio:

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Backend** | FastAPI + Python 3.12 | Same stack as Video Studio. |
| **TTS Engine** | `[TODO]` | Local model (XTTS v2, Piper, etc.). |
| **Audio processing** | `pydub` | Concatenation, silence insertion, normalization, MP3 export. |
| **Waveform** | `[TODO]` | Web Audio API (frontend) or `librosa` (backend) for waveform data. |
| **Frontend** | React 19 + Vite + Tailwind v4 + shadcn/ui | Same design system. |
| **State** | Server-side (SQLite) | Same pattern as Video Studio. |
| **GPU** | RTX 3060M (CUDA) | Required for real-time inference. CPU fallback may be too slow. |

---

## 10. Design System Notes

- Reuses all tokens from `DESIGN.md` (colors, typography, spacing, components, shapes).
- Primary actions (Generate, Export, Play) use amber (`#F0A040`).
- Secondary actions (Add Voice, Split, Regenerate) use ghost or secondary buttons.
- The Preview Bar is a persistent bottom panel with `surface-dim` background and a `divider` top border.
- Segment status badges use `badge-info` (pending), `badge-success` (generated), `badge-error` (failed).
- The waveform visualization uses `surface-variant` background with `secondary` (amber) waveform lines.

---

*End of Draft. Sections marked [TODO] are open for future iteration.*
