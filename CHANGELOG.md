# Changelog

All notable changes to the Conduit project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — Session 3: Video Generation (Planned)

### Planned
- Step 5 Video Generation — ffmpeg pipeline, 1080p24 H.264, concat
- Caption burning (optional, per-segment)
- SRT download at Step 5
- Per-segment random motion effects (pan/zoom)
- User override for motion effects
- Step 1 frontend (deferred from Session 2)
- Complete wizard navigation with Next/Back buttons

---

## [0.2.0] — 2026-06-03 — Session 2: Wizard Body (Steps 2-4)

### Added

#### Backend — AI Integration
- **Fireworks AI Client** (`backend/services/fireworks.py`) — Async wrapper around OpenAI-compatible API with:
  - `base_url` override to `https://api.fireworks.ai/inference/v1`
  - 3x retry with exponential backoff (1s, 2s, 4s)
  - `json_schema` support with flat schema validation (strips `oneOf`, `pattern`, `minLength`, `maxLength`, `minItems`, `maxItems`)
  - `max_tokens` default 2048, override per call
  - Model: `accounts/fireworks/routers/kimi-k2p6-turbo`
  - Error handling: 401 raises immediately, 429/500/503 retries

#### Backend — Character Endpoints (Step 2)
- **Character Extraction** (`POST /api/v1/projects/{uuid}/characters/extract`)
  - Reads `source_of_truth_script.txt` from `.conduit/`
  - Sends to Fireworks AI with flat JSON schema
  - Saves `characters.json` with `name`, `type`, `importance`, `description`
  - Updates `state.json` sub-step: `step_2_call_1_complete = true`
  - Main SQLite state remains `step_1_complete`

- **Character Prompt Generation** (`POST /api/v1/projects/{uuid}/characters/prompts`)
  - Reads `characters.json` from Call 1
  - Generates `front_profile_prompt` and `turnaround_prompt` per character
  - Merges prompts into existing `characters.json` (preserves extraction data)
  - Updates main SQLite state to `step_2_complete`
  - Updates `state.json` sub-step: `step_2_call_2_complete = true`

- **Character Update** (`PUT /api/v1/projects/{uuid}/characters`)
  - Accepts edited character list
  - Persists to `characters.json`

#### Backend — Segment Endpoints (Step 3)
- **Segment Breakdown** (`POST /api/v1/projects/{uuid}/segments/breakdown`)
  - Reads `source_of_truth_script.txt` + `words.json` from `.conduit/`
  - Sends to Fireworks AI with flat JSON schema
  - Saves `segments.json` with `segment_index`, `script_line`, `start_time`, `end_time`, `duration`
  - Updates `state.json` sub-step: `step_3_pass_1_complete = true`
  - Main SQLite state remains `step_2_complete`

- **Segment Prompt Generation** (`POST /api/v1/projects/{uuid}/segments/prompts`)
  - Reads `segments.json` + `characters.json`
  - Single call primary approach (all segments in one call)
  - Fallback: overlapping batches (25 segments, 5 overlap) on 413/token limit
  - Updates `segments.json` with `segment_prompt` and `characters_present`
  - Updates main SQLite state to `step_3_complete`
  - Updates `state.json` sub-step: `step_3_pass_2_complete = true`

- **Segment Update** (`PUT /api/v1/projects/{uuid}/segments`)
  - Accepts edited segment list with re-indexing

- **Segment Split** (`POST /api/v1/projects/{uuid}/segments/{segment_index}/split`)
  - Splits segment at `word_index` or `timestamp`
  - Updates `segments.json` and re-indexes

- **Segment Merge** (`POST /api/v1/projects/{uuid}/segments/{segment_index}/merge`)
  - Merges segment with next segment
  - Updates timing and re-indexes

#### Backend — Image Endpoints (Step 4)
- **Image Upload** (`POST /api/v1/projects/{uuid}/images/{segment_index}`)
  - Accepts multipart PNG upload
  - Validates MIME type (`image/png` only)
  - Validates aspect ratio (16:9 within 1% tolerance)
  - Warns if resolution < 1920×1080 (still accepts)
  - Auto-converts RGBA → RGB (white background compositing)
  - Saves as `{segment_index:04d}.png` in `images/` directory
  - Updates `segments.json` with `image_path`

- **Image Retrieval** (`GET /api/v1/projects/{uuid}/images/{segment_index}`)
  - Returns image file with `image/png` content type

#### Backend — Cascade Logic (Step 2-4)
- **Sub-step Tracking** (`backend/services/state.py`)
  - Added `get_sub_step_state(uuid)` — reads sub-step progress from `state.json`
  - Added `set_sub_step_state(uuid, key, value)` — writes sub-step progress
  - Sub-step keys: `step_2_call_1_complete`, `step_2_call_2_complete`, `step_3_pass_1_complete`, `step_3_pass_2_complete`, `step_4_images_uploaded`

- **Enhanced Cascade Invalidation**
  - Step 2: reset to `step_1_complete`, delete `segments.json`, clear Step 3 + 4 sub-steps
  - Step 3: reset to `step_2_complete`, clear Step 4 sub-steps, preserve images
  - Step 4: reset to `step_3_complete`, clear Step 5 sub-steps, preserve all files
  - Preserves uploaded images on disk during all invalidations

#### Frontend — Step 2 Characters Page
- **`frontend/src/pages/Step2Characters.tsx`**
  - Extract Characters button (amber, primary) with loading spinner
  - Character table (Name, Type, Importance, Description) with editable descriptions
  - Save Changes button (calls `PUT /characters`)
  - Generate Prompts button (enabled after edits)
  - Prompt cards with Front Profile Prompt and Turnaround Reference Prompt
  - Copy buttons per prompt (clipboard API with fallback)
  - JSON toggle per card (shows raw character JSON)
  - Error handling with retry button
  - All icons from `@phosphor-icons/react` (no `lucide-react`)

#### Frontend — Step 3 Segments Page
- **`frontend/src/pages/Step3Segments.tsx`**
  - Generate Segments button (amber, primary) with loading spinner
  - Segment table (Segment #, Script Line, Start → End, Duration, Prompt, Characters, Actions)
  - Editable prompts via inline textarea with auto-save on blur
  - Generate Prompts button (enabled after breakdown)
  - Split button with configurable split point (number input, midpoint default)
  - Merge button (disabled for last segment)
  - Characters displayed as `@Name` tags in teal (`#06B6D4`) with `JetBrains Mono`
  - Error handling with retry button

#### Frontend — Step 4 Images Page
- **`frontend/src/pages/Step4Images.tsx`**
  - Grid view of all segments
  - Each cell: segment number, thumbnail (or grey placeholder), Upload button, Details button
  - Hidden file input with `accept="image/png"`
  - Upload triggers `POST /api/v1/projects/{uuid}/images/{segment_index}`
  - After upload: re-checks image status and displays thumbnail
  - Details modal: script line, segment prompt, characters present, timing
  - Grey placeholder (`bg-[#2A2A35]`) for missing images

#### Frontend — WizardShell Routing
- Updated `frontend/src/components/WizardShell.tsx` with:
  - `useParams` + `useEffect` URL sync for step state
  - `switch/case` rendering for Steps 2, 3, 4
  - Step 2: `Step2Characters`
  - Step 3: `Step3Segments`
  - Step 4: `Step4Images`

#### Testing
- **Backend Tests:** `test_characters.py` (8 tests), `test_segments.py` (14 tests), `test_images.py` (9 tests), `test_fireworks.py` (9 tests)
  - All use `httpx.AsyncClient` + `respx` for mocking
  - Coverage: happy path, error cases, retry logic, partial state, batch fallback

- **Frontend Tests:** `step2.spec.ts` (5 tests), `step3.spec.ts` (8 tests), `step4.spec.ts` (7 tests)
  - Playwright E2E with visual assertions
  - Mock API responses with `page.route()`
  - Tests: button visibility, table rows, edit interactions, copy buttons, JSON toggle, split/merge, grid cells, upload flow, details modal

### Changed
- **Backend routers (`backend/routers/__init__.py`)** — Added `characters_router`, `segments_router`, `images_router` registration
- **Backend state (`backend/services/state.py`)** — Added sub-step tracking and enhanced cascade logic without modifying `ProjectState` enum
- **Frontend tests** — Total: 34 tests (up from 14 in Session 1)
- **Backend tests** — Total: 51 tests (up from 8 in Session 1)

### Fixed
- **Windows path separators** — Test assertions updated to accept both `/` and `\`
- **Parallel task conflicts** — `routers/__init__.py` was missing imports due to concurrent modifications; fixed by adding both `segments_router` and `images_router`
- **RGB conversion** — Added white background compositing for RGBA → RGB: `Image.new("RGB", image.size, (255,255,255))` then paste with alpha mask

### Design System Compliance
- Zero border-radius throughout (`0px` on all buttons, cards, modals, tables, upload zones)
- No shadows, no gradients
- Dark theme: `#0F0F14` surface, `#F0A040` amber accent, `#06B6D4` teal info
- Fonts: Playfair Display (headlines), Source Sans 3 (body), JetBrains Mono (technical)
- All icons from `@phosphor-icons/react` (no `lucide-react` in source code)
- `radius: 0` in `components.json`

---

## [0.1.0] — 2026-06-03 — Session 1: Foundation

### Added

#### Project Structure
- `backend/` directory with subdirectories: `models/`, `services/`, `routers/`, `tests/`, `utils/`
- `frontend/` directory with Vite + React + Tailwind v4 + shadcn/ui
- `backend/requirements.txt` with 11 pinned packages
- `backend/.env.example` with `OPENAI_API_KEY` and `FIREWORKS_API_KEY` placeholders
- `.sisyphus/` directory for plan tracking, evidence, and notepads

#### Backend — FastAPI Foundation
- **`backend/main.py`** — FastAPI app with:
  - `GET /health` endpoint returning `{"status": "ok"}`
  - `APIRouter` at `/api/v1`
  - `CORSMiddleware` allowing `http://localhost:5173`
  - Global exception handler returning JSON (not HTML)
  - Startup validation: raises `RuntimeError` if `OPENAI_API_KEY` missing

- **`backend/models/database.py`** — aiosqlite connection with:
  - `pragma journal_mode=WAL`
  - `check_same_thread=False`
  - `schema_version` table for migrations
  - `projects` table: `uuid`, `name`, `state`, `created_at`, `updated_at`, `voiceover_path`, `script_path`

- **`backend/models/project.py`** — Pydantic models:
  - `ProjectCreate`: `name` (min 1 char, max 100)
  - `ProjectResponse`: `uuid`, `name`, `state`, `created_at`, `updated_at`
  - `ProjectListResponse`: `projects: List[ProjectResponse]`

- **`backend/models/state.py`** — `ProjectState` enum:
  - `created`, `step_1_complete`, `step_2_complete`, `step_3_complete`, `step_4_complete`, `step_5_complete`

- **`backend/services/state.py`** — Cascade state machine:
  - `update_state(uuid, new_state)` — validates transitions
  - `invalidate_downstream(uuid, edited_step)` — resets Steps N+1 through 5
  - `get_state(uuid)` — returns current state
  - Preserves images during invalidation

- **`backend/routers/projects.py`** — Project CRUD endpoints:
  - `POST /api/v1/projects` — create project, auto-generate UUID, create directory tree
  - `GET /api/v1/projects` — list all projects
  - `GET /api/v1/projects/{uuid}` — get single project
  - `DELETE /api/v1/projects/{uuid}` — delete project + directory
  - Creates directory tree: `./projects/{uuid}/`, `images/`, `output/`, `.conduit/`
  - Saves `project.json` and `state.json` in `.conduit/`

#### Backend — Whisper API Integration (Step 1)
- **`backend/services/whisper.py`** — Whisper API integration:
  - `transcribe_audio(file_path)` — calls `whisper-1` with `verbose_json` and `timestamp_granularities=["word"]`
  - Returns word-level timestamps

- **`backend/services/chunking.py`** — pydub audio chunking:
  - `chunk_audio(file_path, max_bytes=25_000_000)` — splits on silence boundaries
  - Uses `pydub.silence.detect_nonsilent()` for speech segments
  - Merges short segments to stay under 25MB
  - Exports temporary WAV files, cleans up after transcription

- **`backend/services/srt.py`** — SRT generation:
  - `generate_srt(words)` — groups words into sentences, ≤42 chars per line, 1-2 sentences per caption
  - Uses `srt` library for valid format
  - Saves `captions.srt`, `words.json`, `transcript_raw.txt` to project directory

- **`backend/routers/projects.py`** — Voiceover endpoint:
  - `POST /api/v1/projects/{uuid}/voiceover` — accepts multipart file, saves to `voiceover.mp3`
  - `GET /api/v1/projects/{uuid}/status` — polling endpoint for processing state

#### Frontend — Vite + React + Tailwind v4
- `npm create vite@latest frontend -- --template react-ts`
- Dependencies: `react-router-dom`, `@phosphor-icons/react`, `@fontsource/*`
- DevDependencies: `vite`, `tailwindcss`, `@tailwindcss/vite`, `typescript`, `@vitejs/plugin-react`, `playwright`
- `frontend/vite.config.ts` with Tailwind plugin
- `frontend/src/styles/index.css` with `@import "tailwindcss"`
- Font imports in `frontend/src/main.tsx`: Playfair Display (400, 700), Source Sans 3 (400, 600), JetBrains Mono (400)
- Self-hosted fonts (no Google Fonts `<link>` tags)

#### Frontend — shadcn/ui
- `npx shadcn@latest init` with `radius: 0`
- `iconLibrary: "lucide"` in `components.json` (all generated components require manual icon replacement)
- Test component: `frontend/src/components/ui/button.tsx`

#### Frontend — Theme System
- **`frontend/src/styles/theme.css`** — CSS custom properties:
  - `--color-primary: #0F0F14`
  - `--color-secondary: #F0A040`
  - `--color-tertiary: #06B6D4`
  - `--color-surface: #0F0F14`
  - `--color-surface-dim: #0A0A0F`
  - `--color-surface-bright: #1A1A24`
  - `--color-surface-variant: #1E1E28`
  - `--color-on-surface: #E8E8F0`
  - `--color-on-surface-variant: #8A8A9A`
  - `--color-on-surface-dim: #5A5A6A`
  - `--color-error: #EF4444`
  - `--color-success: #22C55E`
  - `--color-warning: #EAB308`
  - `--color-border: #2A2A35`
  - `--color-divider: #1A1A24`
  - `--color-input-placeholder: #8A8A9A`
- Global `border-radius: 0px` on all buttons, inputs, cards
- Body background: `#0F0F14`

#### Frontend — Wizard Shell
- **`frontend/src/components/WizardShell.tsx`** — Layout:
  - Title Bar (48px): App name "Conduit" (Playfair Display, 24px), project name, status indicator
  - Stepper Bar (56px): 5 steps, active=amber, completed=teal, pending=dim
  - Main Content Area (flex-1, scrollable)
  - Action Bar (64px): Back button (secondary), Next button (primary amber)

- **`frontend/src/components/Stepper.tsx`** — 5-step stepper:
  - Step 1: Script (FileText icon)
  - Step 2: Characters (User icon)
  - Step 3: Segments (Scissors icon)
  - Step 4: Images (Image icon)
  - Step 5: Video (FilmStrip icon)
  - Active: amber (`#F0A040`), Completed: teal (`#06B6D4`), Pending: dim

#### Frontend — Dashboard
- **`frontend/src/pages/Dashboard.tsx`** — Project list page:
  - Empty state: 3 overlapping sharp rectangles (geometric illustration) in `surface-variant` and `on-surface-dim` colors
  - Empty state text: "No projects yet. Create your first project to get started."
  - Project cards: name (H2, Playfair Display), created date (mono-sm), status badge, Open button (ghost, teal), Delete button (ghost, Trash icon)
  - "Create Project" button (primary, amber, large)
  - Fetches from `GET /api/v1/projects`

#### Frontend — Routing
- **`frontend/src/App.tsx`** — React Router:
  - `/` → `Dashboard`
  - `/project/:uuid` → `WizardShell`
  - `/project/:uuid/step/:stepNumber` → `WizardShell`

#### Testing
- **Backend Tests:** `test_projects.py` (8 tests)
  - `test_create_project_valid` — assert `201`
  - `test_create_project_empty_name` — assert `422`
  - `test_list_projects` — assert `200` and list length >= 1
  - `test_get_project` — assert `200`
  - `test_delete_project` — assert `204`
  - `test_cascade_state_machine` — update + invalidate
  - `test_whisper_mock_respx` — assert `model="whisper-1"`
  - `test_get_project_not_found` — assert `404`

- **Frontend Tests:** `wizard.spec.ts` (9 tests), `dashboard.spec.ts` (5 tests)
  - Wizard: renders Conduit heading, 5-step stepper, active/completed colors, border-radius 0px, fonts, body background
  - Dashboard: empty state with 3 rectangles, Create Project button amber, project card with name/date/badge/buttons

### Design System
- Dark cinematic UI: `#0F0F14` surface, `#F0A040` amber, `#06B6D4` teal
- Typography: Playfair Display (headlines), Source Sans 3 (body), JetBrains Mono (technical)
- Zero border-radius (`0px`)
- No shadows, no gradients
- `@phosphor-icons/react` (never `lucide-react`)
- Tailwind v4 with CSS-based config (no `tailwind.config.js`)

### Known Issues
- **OpenAI API key invalid** — `sk-proj-...` key returns `401 AuthenticationError`. Needs valid key from https://platform.openai.com/api-keys. Not blocking for Session 2 (uses Fireworks). Session 3 concern for Whisper transcription.
- **shadcn/ui Tailwind v4 compatibility** — CLI works but may need manual fixes. Pre-flight validated.
- **ffmpeg** — Not initially in PATH; user added. Version 4.0 (older than recommended 6.x but functional).

---

## Session Overview

### Session 1 (2026-06-03) — Foundation
**Goal:** Build project skeleton (FastAPI + React/Vite), backend core (SQLite + CRUD + state machine), frontend shell (wizard + dashboard + theme), Whisper API integration.
**Status:** ✅ COMPLETE — 16 tasks, 3 waves, 4-phase verification passed.
**Deliverables:** Running backend at `localhost:8000`, running frontend at `localhost:5173`, 8 backend tests + 14 frontend tests.

### Session 2 (2026-06-03) — Wizard Body (Steps 2-4)
**Goal:** Build Steps 2–4 of wizard: Character extraction (2 Fireworks calls), Segment generation (2 passes), Image uploading. Skip Step 1 frontend (deferred to Session 3).
**Status:** ✅ COMPLETE — 16 tasks, 3 waves, 4-phase verification passed.
**Deliverables:** Fireworks AI client, character/segment/image endpoints, cascade logic for Steps 2–4, frontend pages for Steps 2–4, 51 backend tests + 34 frontend tests.

### Session 3 (Planned) — Video Generation
**Goal:** Step 5 video generation (ffmpeg pipeline), Step 1 frontend, caption burning, SRT download.
**Status:** PENDING

### Session 4 (Planned) — Polish
**Goal:** UI refinements, cascade warning UI, accessibility, end-to-end testing.
**Status:** PENDING

---

## File Inventory

### Backend (22 Python files)
```
backend/main.py
backend/models/database.py
backend/models/project.py
backend/models/state.py
backend/models/__init__.py
backend/routers/__init__.py
backend/routers/projects.py
backend/routers/characters.py
backend/routers/segments.py
backend/routers/images.py
backend/services/__init__.py
backend/services/fireworks.py
backend/services/whisper.py
backend/services/chunking.py
backend/services/srt.py
backend/services/state.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/test_projects.py
backend/tests/test_characters.py
backend/tests/test_segments.py
backend/tests/test_images.py
backend/tests/test_fireworks.py
backend/utils/__init__.py
```

### Frontend (10 TSX files + 5 test files)
```
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/components/WizardShell.tsx
frontend/src/components/Stepper.tsx
frontend/src/components/ui/button.tsx
frontend/src/pages/Dashboard.tsx
frontend/src/pages/Step2Characters.tsx
frontend/src/pages/Step3Segments.tsx
frontend/src/pages/Step4Images.tsx
frontend/src/styles/theme.css
frontend/src/styles/index.css
frontend/tests/dashboard.spec.ts
frontend/tests/wizard.spec.ts
frontend/tests/step2.spec.ts
frontend/tests/step3.spec.ts
frontend/tests/step4.spec.ts
```

### Design & Planning
```
DESIGN.md
DESIGN_SPEC.md
v1-roadmap.md
CHANGELOG.md
backend/.env.example
frontend/components.json
.sisyphus/plans/6-3-26_foundation.md
.sisyphus/plans/session-2.md
.sisyphus/assignments/6-3-26_foundation.md
.sisyphus/assignments/session-2.md
.sisyphus/notepads/session-2/learnings.md
```

---

## Test Coverage

| Session | Backend Tests | Frontend Tests | Total |
|---------|--------------|----------------|-------|
| Session 1 | 8 | 14 | 22 |
| Session 2 | 51 | 34 | 85 |

### Backend Test Breakdown
- `test_fireworks.py` — 9 tests (client, base_url, retry logic, json_schema, error handling)
- `test_characters.py` — 8 tests (extract, prompts, missing script, prerequisite, failures, update)
- `test_segments.py` — 14 tests (breakdown, prompts, split, merge, missing files, prerequisite, failures, batch fallback)
- `test_images.py` — 9 tests (upload, non-PNG, wrong ratio, RGBA, low resolution, GET, not found)
- `test_projects.py` — 11 tests (CRUD, cascade, state machine, Whisper mock, not found)

### Frontend Test Breakdown
- `dashboard.spec.ts` — 5 tests (empty state, Create Project button, project card, fonts, background)
- `wizard.spec.ts` — 9 tests (heading, stepper, colors, border-radius, fonts, background)
- `step2.spec.ts` — 5 tests (extract button, table rows, edit, copy, JSON toggle)
- `step3.spec.ts` — 8 tests (generate button, table rows, editable prompts, split/merge, error, prompts button, radius, font)
- `step4.spec.ts` — 7 tests (grid cells, upload button, details button, placeholder, thumbnail, details modal, upload flow)

---

## API Endpoints

### Projects
- `POST /api/v1/projects` — Create project
- `GET /api/v1/projects` — List projects
- `GET /api/v1/projects/{uuid}` — Get project
- `DELETE /api/v1/projects/{uuid}` — Delete project
- `POST /api/v1/projects/{uuid}/voiceover` — Upload voiceover
- `GET /api/v1/projects/{uuid}/status` — Get processing status

### Characters
- `POST /api/v1/projects/{uuid}/characters/extract` — Extract characters from script
- `POST /api/v1/projects/{uuid}/characters/prompts` — Generate character prompts
- `PUT /api/v1/projects/{uuid}/characters` — Update characters

### Segments
- `POST /api/v1/projects/{uuid}/segments/breakdown` — Breakdown segments
- `POST /api/v1/projects/{uuid}/segments/prompts` — Generate segment prompts
- `PUT /api/v1/projects/{uuid}/segments` — Update segments
- `POST /api/v1/projects/{uuid}/segments/{segment_index}/split` — Split segment
- `POST /api/v1/projects/{uuid}/segments/{segment_index}/merge` — Merge segments

### Images
- `POST /api/v1/projects/{uuid}/images/{segment_index}` — Upload image
- `GET /api/v1/projects/{uuid}/images/{segment_index}` — Get image

### Health
- `GET /health` — Health check

---

## Tech Stack

### Backend
- Python 3.12.10
- FastAPI 0.115.0
- Uvicorn 0.34.0
- Pydantic 2.10.0
- aiosqlite 0.21.0 (WAL mode)
- OpenAI SDK 1.60.0 (with `base_url` override for Fireworks)
- pydub 0.25.1
- srt 3.5.3
- pytest 8.3.0 + pytest-asyncio 0.24.0 + respx 0.22.0
- Pillow (for image processing)

### Frontend
- React 19
- Vite 8.0.16
- Tailwind CSS v4.3.0
- shadcn/ui (base-nova, radius=0)
- React Router DOM
- @phosphor-icons/react
- @fontsource/* (self-hosted fonts)
- Playwright (E2E testing)
- TypeScript

### Infrastructure
- SQLite (file-based, WAL mode)
- ffmpeg 4.0 (for video generation, Session 3)
- No Docker, no cloud, no auth
- Localhost only: backend `localhost:8000`, frontend `localhost:5173`

---

## Notes for Future Sessions

### Session 3 Dependencies
- Valid OpenAI API key for Whisper transcription (currently invalid)
- ffmpeg 6.x+ recommended (currently 4.0)
- Step 1 frontend (script upload + voiceover upload)
- Video generation pipeline (ffmpeg concat, H.264, 1080p24)

### Session 4 Dependencies
- Cascade warning UI (when editing upstream steps)
- Accessibility audit (WCAG 2.1 AA)
- Mobile responsive breakpoints (optional)
- End-to-end integration testing (full wizard flow)

### Risk Register
- **OpenAI API key invalid** — High priority fix for Session 3
- **ffmpeg version** — Functional but may need upgrade for advanced features
- **shadcn/ui Tailwind v4** — Monitor for breaking changes
- **Fireworks API key** — Valid, but monitor for rate limits

---

*Generated by Atlas on 2026-06-03. Based on .sisyphus plans, notepads, and evidence files.*
