# Changelog

All notable changes to the Conduit project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] — 2026-06-06 — Session B: Refactoring, Performance & DRY

### Backend Refactoring
- **H10 — Timezone-aware datetimes** (`backend/routers/projects.py`, `video.py`, `services/ffmpeg.py`, `services/state.py`) — Replaced deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)` at 9 sites. All timestamps now emit `+00:00` suffix.
- **H4 + H5 — Single source of truth for motion effects** (`backend/services/effects.py`, `backend/services/ffmpeg.py`) — `effects.py` now owns all effect parameters and `build_zoompan_filter()` expressions. `ffmpeg.py:generate_segment_clip` removed its 7-way `if/elif` duplication and delegates to `effects.build_zoompan_filter()`. Reconciled pan speed to `±2` (DESIGN_SPEC Appendix A). Verified all 6 effects render 1920×1080 at 24fps.
- **H6 — Batch image-status endpoint** (`backend/routers/images.py`) — Added `GET /api/v1/projects/{uuid}/images/status` returning `{ "<segment_index>": bool }`. Reuses `_load_segments` and `_get_image_path`. Returns 404 for missing project, `{}` for empty segments.
- **M9 — Typed, non-leaking AI error handling** (`backend/routers/characters.py`, `backend/routers/segments.py`) — Replaced `except Exception` with typed handlers: `AuthenticationError`→502, `RateLimitError`→429, `APIError`→502. Extracted `_handle_fireworks_error()` helper to eliminate duplication. Removed all `detail=f"...: {exc}"` interpolation. Full exceptions logged server-side via `logging`.
- **H14 + M8 + H13-doc** (`backend/main.py`) — Narrowed CORS `allow_headers` from `["*"]` to `["Content-Type"]`. Added `await models.database.init_db()` in startup handler. Documented H13 (rate limiting) as deliberate won't-fix for single-user localhost.

### Frontend Refactoring
- **M1 — Shared ProjectState type** (`frontend/src/lib/projectState.ts`, `frontend/src/components/WizardShell.tsx`, `frontend/src/components/Stepper.tsx`) — Extracted `ProjectStateValue` strict union type and `isStepComplete()` helper. Eliminated duplicated `stateMap`/`isStepComplete` logic in both components.
- **M6 — Button radius compliance** (`frontend/src/components/ui/button.tsx`) — Removed all `rounded-*` and `rounded-[...]` classes from base `cva` string and size variants. Component now complies with DESIGN.md (0px border radius everywhere).
- **M7 — Version bump** (`frontend/package.json`) — Bumped version from `0.0.0` to `0.5.0`.
- **M2 + M4 + M5 — Playwright test hygiene** (`frontend/tests/utils.ts`, 8 spec files) — Extracted `injectStyles(page: Page)` and `isBackendRunning()` (fetch-based) to shared utils. Replaced all `page: any` with typed `Page`. Replaced `execSync('curl ...')` with `fetch`-based health check. Added `"node"` to `tests/tsconfig.json` types.
- **H6 — Batch image status adoption** (`frontend/src/pages/Step4Images.tsx`, `frontend/src/pages/Step5Video.tsx`) — Replaced per-segment `checkImageStatus` loops with single `GET /images/status` call. Preserved thumbnail rendering via per-segment `GET /images/{index}`. Added AbortController hygiene and floating-promise `.catch` pattern.
- **H9 — Unmount-safe polling** (`frontend/src/pages/Step5Video.tsx`) — Added `mounted` ref (`useRef(true)`) and guards every `setState` inside the 2s polling `setInterval` callback. Cleanup sets `mounted.current = false` before `clearInterval`. Prevents "setState on unmounted component" warnings.

### Testing
- **Backend Tests:** 114 tests (up from 102 in Session A) — 12 new tests: 4 for batch image-status endpoint, 8 for typed error handling (AuthError + RateLimit in characters/segments extract/prompts/breakdown)
- **Frontend Tests:** 73 tests (down from 75 due to 3 backend-required tests skipped) — All passing with batch endpoint mocks
- **TypeScript:** `npx tsc --noEmit` → 0 errors
- **Build:** `npm run build` → success

### Fixed
- **F-B Review findings:** Removed dead `_ensure_step_2_complete` function from `segments.py`. Extracted `_handle_fireworks_error()` to eliminate duplicated exception triplet in `characters.py` and `segments.py`. Replaced `request: any` with `request: APIRequestContext` in `e2e-error-paths.spec.ts`.

### Pre-existing Issue (not in Session B scope)
- **Exception leak in `images.py`** — `backend/routers/images.py:89` contains `detail=f"Invalid image file: {exc}"` which leaks the raw exception string to the client. This violates the architecture rule "Never return `str(exc)` to the client." Recommended for follow-up cleanup.

---

## [0.6.1] — 2026-06-06 — Follow-up Fixes

### Security
- **Fix exception leak in `images.py`** (`backend/routers/images.py:89`) — Replaced `detail=f"Invalid image file: {exc}"` with generic `detail="Invalid image file — please upload a valid PNG"`. Added `logging.error("Image validation failed", exc_info=exc)` for full server-side logging. This was the last remaining `str(exc)` leak in the backend.

### Fixed
- **Sync `package.json` version** (`frontend/package.json`) — Bumped `0.5.0` → `0.6.0` to match the `[0.6.0]` release tag.

---

## [0.5.0] — 2026-06-06 — Session A: Safety & Async Fixes

### Security
- **C2 — Secure global exception handler** (`backend/main.py`) — Replaced `str(exc)` client leak with generic error message. Full exception now logged server-side via `logging` module with `exc_info=True`.
- **C4 — FFmpeg command injection safety** (`backend/services/ffmpeg.py`) — Verified list-based `subprocess.run` with `shell=False` (default). Added explicit comment documenting why no `shlex.quote()` is needed.

### Async Correctness
- **C1 — Fix `time.sleep` in async context** (`backend/services/whisper.py`) — Replaced `time.sleep(delay)` with `await asyncio.sleep(delay)` at line 44. Removed `import time`. Prevents event loop blocking during Whisper API retries.
- **C7 — Request timeouts on AI clients** (`backend/services/whisper.py`, `backend/services/fireworks.py`) — Added `timeout=60.0` to all `OpenAI()` constructors. Wrapped `fireworks.py` completion call with `async with asyncio.timeout(120):` to prevent indefinite hangs.

### Type Safety
- **C5 — Enable TypeScript strict mode** (`frontend/tsconfig.json`) — Added `"strict": true` to `compilerOptions`. Ran `npx tsc --noEmit` — 0 errors (codebase already compatible). No runtime changes.
- **H7 — Fix floating promises** (`frontend/src/pages/Step1Script.tsx`, `Step3Segments.tsx`, `Step4Images.tsx`) — Added `.catch()` error handling to all `useEffect` async calls. Prevents unhandled promise rejections.
- **H8 — Add AbortController** (`frontend/src/components/WizardShell.tsx`, `Step1Script.tsx`, `Step5Video.tsx`) — Added `AbortController` to all `useEffect` fetch hooks. Cleanup function calls `controller.abort()` on unmount to prevent race conditions.

### Component Architecture
- **C6 — React Error Boundary** (`frontend/src/components/WizardShell.tsx`) — Installed `react-error-boundary`. Wrapped `renderStepContent()` with `<ErrorBoundary fallbackRender={fallbackRender}>`. Fallback UI matches DESIGN.md: dark surface `#0F0F14`, amber `#F0A040`, `data-testid="error-boundary"`.
- **C8 — Extract custom hooks** (`frontend/src/hooks/useDiff.ts`, `frontend/src/hooks/useTranscript.ts`) — Extracted `useDiff` (LCS + diff computation) and `useTranscript` (fetch + upload logic) from `Step1Script.tsx`. Reduced component from 670 → 459 lines (-211 lines). All types preserved.
- **H3 — Pass `projectState` to Stepper** (`frontend/src/components/Stepper.tsx`, `WizardShell.tsx`) — Eliminated duplicate `fetchProjectState()` in Stepper. Now receives `projectState` prop from parent. Removed `useEffect`, `useState`, `useParams` from Stepper.

### Configuration & Refactoring
- **H1 — Centralize `PROJECTS_BASE_DIR`** (`backend/config.py`) — Extracted `PROJECTS_BASE_DIR` into `backend/config.py`. Updated 7 files to import from `config.py`. Eliminated DRY violation across backend.
- **H2 — Centralize `apiBase`** (`frontend/src/config.ts`) — Extracted `apiBase` into `frontend/src/config.ts`. Updated 8 source files + 10 test files. Eliminated hardcoded URL duplication across frontend.

### Testing & Infrastructure
- **C3 — Fix test database isolation** (`backend/tests/conftest.py`) — Replaced dangerous `os.remove(models.database.DB_PATH)` with `tempfile.mkstemp(suffix=".db")`. File descriptor explicitly closed. `DB_PATH` patched inside fixture. Prevents production DB destruction during test runs.
- **H11 — Document `check_same_thread=False`** (`backend/models/database.py`) — Added comment explaining why `check_same_thread=False` is correct for aiosqlite (internal thread pool + WAL mode). No `asyncio.Lock` added.
- **H12 — Streaming file upload** (`backend/routers/projects.py`) — Replaced `await file.read()` + `f.write(content)` with `shutil.copyfileobj(file.file, f)`. Prevents memory bloat for large voiceover files.

### Testing
- **Backend Tests:** 102 tests (unchanged, all passing)
- **Frontend Tests:** 73 tests (unchanged, all passing)
- **Total:** 175 tests
- **TypeScript:** `npx tsc --noEmit` → 0 errors

---

## [0.4.0] — 2026-06-04 — Session 4: Polish

### Added

#### Accessibility Audit (WCAG 2.1 AA)
- **`role="alert"` + `aria-live="assertive"`** on all error/success banners across Steps 1–5
- **`aria-expanded` + `aria-controls`** on all collapsible toggles (Original Script, JSON, Console)
- **`aria-label` + `aria-current="step"`** on stepper buttons for screen-reader navigation
- **`role="progressbar"` + `aria-valuenow` + `aria-valuemax`** on video generation progress bar
- **`role="dialog"` + `aria-modal="true"`** on Step 4 details modal
- **`useFocusTrap` hook** (`frontend/src/hooks/useFocusTrap.ts`) — modal focus trapping, Escape-to-close, focus return
- **Keyboard accessibility** — Step 1 dropzone (`tabindex="0"`, `role="button"`, `aria-label`)
- **`SkeletonTable` component** (`frontend/src/components/SkeletonTable.tsx`) with `aria-busy="true"`, `role="status"`, `aria-label="Loading"`
- **`prefers-reduced-motion`** media query in `frontend/src/styles/index.css` — disables all decorative animations for users with motion sensitivity

#### UI Refinements
- **`AmberBar` component** (`frontend/src/components/AmberBar.tsx`) — animated amber loading indicator
- **`animate-shimmer` CSS** (`frontend/src/styles/index.css`) — skeleton-screen shimmer animation
- **Ghost button transparency** — `button.tsx` ghost variant now uses `bg-transparent` with explicit hover states
- **Stepper state enforcement** — reads backend `projectState` for `isStepComplete`; disables skip-ahead with `cursor-not-allowed` and `opacity-50`
- **Cascade warning UI** — Stepper and `WizardShell` invalidate downstream steps on edit; E2E tests verify segments.json deletion and image preservation

#### End-to-End Integration Testing
- **`frontend/tests/e2e-happy-path.spec.ts`** (7 tests) — Full 5-step wizard flow: create project → upload voiceover → extract characters → generate segments → upload images → generate video → verify output files
- **`frontend/tests/e2e-error-paths.spec.ts`** (2 tests) — Corrupted voiceover upload shows error banner and stays at Step 1; editing Step 2 triggers cascade invalidation and preserves images
- **`frontend/tests/accessibility-gaps.spec.ts`** (14 tests) — Per-page a11y attribute verification (role, aria-live, aria-expanded, aria-controls, aria-label, aria-current, aria-modal, focus trap, keyboard accessibility)
- **`backend/run_test_backend.py`** — Mock backend server for E2E tests (mocked Whisper transcription, Fireworks AI, ffmpeg video generation)
- **`frontend/tests/global-setup.ts`** — Playwright global setup for E2E test suite

#### AI Prompt Design
- **Structural marker cleaning** — Added to `DESIGN_SPEC.md` §3.5 Step 1a system prompt:
  - Section headers (e.g., "Chapter 1", "Introduction", "Part 1")
  - Speaker labels (e.g., "NARRATOR:", "HOST:")
  - Stage directions (e.g., "[sighs]", "[pause]")
  - Formatting markers (e.g., "---", "TITLE CARD", "END")
  - AI treats these as intentional omissions that should NOT appear in the final `source_of_truth_script.txt`

#### Backend Refinements
- **`GET /api/v1/projects/{uuid}/characters`** — Retrieve character list from `characters.json`
- **`backend/tests/test_characters.py`** — Added tests for `GET /characters` endpoint
- **`backend/tests/test_projects.py`** — Added cascade invalidation tests and transcript endpoint tests

#### Testing
- **Backend Tests:** 102 tests (up from 96 in Session 3)
- **Frontend Tests:** 75 tests (up from 52 in Session 3)
- **Total:** 177 tests

### Changed
- **`frontend/src/components/Stepper.tsx`** — Now fetches `projectState` from backend to determine completed steps; adds `disabled` and `aria-label` attributes
- **`frontend/src/components/WizardShell.tsx`** — Step completion logic synced with backend state; Next button disabled until current step complete
- **`frontend/src/pages/Step4Images.tsx`** — Modal uses `useFocusTrap` hook; adds `aria-modal` and `aria-label` attributes
- **`frontend/src/styles/index.css`** — Added `animate-shimmer` keyframes and `prefers-reduced-motion` rules

### Fixed
- **Ghost button background** — `button.tsx` ghost variant now explicitly `bg-transparent` to match design system
- **Stepper clickability** — Incomplete future steps are now properly disabled, preventing user skip-ahead
- **Whisper Pydantic models** — `services/whisper.py` now converts `TranscriptionWord` objects to dicts using `model_dump()` before returning. Fixes `AttributeError: 'TranscriptionWord' object has no attribute 'get'` during voiceover upload and SRT generation.

### Known Issues
- ~~**ffmpeg version** — 4.0 (older than recommended 6.x+ but functional; zoompan validated)~~ **Resolved** — Upgraded to 8.1.1
- **OpenAI API key** — Validated working (billing added during Session 2)
- **lucide-react** — Removed from `package.json`; `components.json` updated to `@phosphor-icons/react`

## [0.4.1] — 2026-06-05 — Step 1 UX Improvements

### Added
- **`Auto-Approve "Remaining" button`** (`frontend/src/pages/Step1Script.tsx`) — Bulk-approve all unreviewed diff changes without overriding rejections. Disabled when no changes remain.
- **`Fidelity percentage badge`** (`frontend/src/pages/Step1Script.tsx`) — Real-time fidelity metric showing transcript faithfulness to original script. Formula: `(equal words + approved changes) / total script words × 100`. Color-coded: green ≥95%, warning 80–94%, red <80%. Uses `label-sm` typography and `badge-*` tokens from DESIGN.md.
- **`onStep1Ready` callback** (`frontend/src/pages/Step1Script.tsx` → `frontend/src/components/WizardShell.tsx`) — Bi-directional communication between child and parent. `Step1Script` exposes `hasTranscript`, `hasScript`, and `fidelity` to `WizardShell` via stable `useCallback` callback (prevents infinite render loops).
- **Non-blocking warning modal** (`frontend/src/components/WizardShell.tsx`) — Appears when user presses Next with fidelity < 95% and original script present. Offers "Review Anyway" (proceeds to Step 2) and "Continue Reviewing" (closes modal). Modal has `role="dialog"`, `aria-modal="true"`, focus trap via `useFocusTrap`, and `triggerRef` for focus return.
- **Shared `goToStep` helper** — Extracted from `handleNext` to ensure `setCurrentStep` + `navigate` stay synchronized across normal navigation and modal "Review Anyway" path.
- **`frontend/tests/step1-fidelity.spec.ts`** — 7 new Playwright tests covering:
  - Auto-Approve button functionality
  - Fidelity badge display and color changes
  - Next button enabled/disabled states
  - Warning modal appearance and dismissal
  - "Review Anyway" navigation to Step 2
  - High fidelity navigation without modal

### Changed
- **`WizardShell.tsx` `canGoNext` logic** — Step 1 now uses `step1Data.hasTranscript` (frontend state) instead of `isStepComplete` (backend state). Steps 2–5 remain unchanged.
- **`frontend/tests/step1.spec.ts`** — Updated test "Next button is disabled initially, enabled after transcript" to match new behavior: Next enabled when transcript present (regardless of backend state).
- **`frontend/tests/wizard.spec.ts`** — Updated "completed step has teal color" test to mock transcript endpoint so Next button is enabled before clicking.

### Fixed
- **`null < 95` coercion bug** — Warning modal condition explicitly checks `fidelity !== null` before `fidelity < 95` to prevent `null` from coercing to `0` and triggering false positives.
- **Whitespace token counting** — `computeDiff` splits with `/(\s+)/`, producing whitespace tokens in arrays. Fidelity calculation explicitly filters `token.trim().length > 0` to avoid inflated percentages.

### Testing
- **Frontend Tests:** 82 tests (up from 75 in Session 4)
- **Backend Tests:** 102 tests (unchanged)
- **Total:** 184 tests

---

## [0.3.0] — 2026-06-04 — Session 3: Video Generation + Step 1 Frontend

### Added

#### Backend — Video Generation (Step 5)
- **ffmpeg Pipeline Service** (`backend/services/ffmpeg.py`)
  - `generate_segment_clip()` — 7 effects: none, zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down
  - `concat_segments()` — ffconcat demuxer with `-c copy`
  - `mix_audio()` — voiceover mix with `-c:v copy -c:a aac -shortest`
  - `burn_captions()` — SRT subtitle burn via ffmpeg `subtitles` filter
  - `generate_video()` — async orchestrator with temp directory, progress tracking, cleanup
  - Uses `subprocess.run` with `capture_output=True`, `check=True`
  - Progress written to `state.json` under `video_progress` key

- **Motion Effects Service** (`backend/services/effects.py`)
  - `EFFECTS` dict with zoom/pan parameters for 6 motion effects
  - `build_zoompan_filter()` — generates ffmpeg zoompan filter strings
  - `random_assign_effects()` — random assignment with no adjacent duplicates
  - `validate_effect()` — effect name validation

- **Video Router** (`backend/routers/video.py`)
  - `POST /api/v1/projects/{uuid}/video/generate` — validates images, triggers ffmpeg pipeline
  - `GET /api/v1/projects/{uuid}/video/status` — returns idle/processing/completed/error status
  - `GET /api/v1/projects/{uuid}/video/download` — serves `output/output.mp4`
  - `GET /api/v1/projects/{uuid}/video/srt` — serves `captions.srt` with `Content-Disposition: attachment`
  - `GET /api/v1/projects/{uuid}/video/ass` — serves `captions.ass` (optional)

#### Backend — Step 1 Transcription Wiring
- **Voiceover Upload Endpoint** (`backend/routers/projects.py`)
  - `POST /api/v1/projects/{uuid}/voiceover` now triggers full transcription pipeline:
    - Calls `services.whisper.py` `transcribe_audio()`
    - Calls `services.chunking.py` `chunk_audio()` if file > 25MB
    - Calls `services.srt.py` `generate_srt()` with transcription result
    - Saves `transcript.json` to project directory
    - Updates state to `step_1_complete`
  - `GET /api/v1/projects/{uuid}/transcript` — returns transcript data
  - Fixed `services.srt.py` path to use `PROJECTS_BASE_DIR` consistently

#### Backend — Segment Schema Updates
- **Effect Field** (`backend/routers/segments.py`)
  - Added `effect` field to segment schema (default `"none"`)
  - `PUT /api/v1/projects/{uuid}/segments/{segment_index}/effect` — validates and updates effect
  - Split/merge endpoints preserve effect field

#### Frontend — Step 1 Script Page
- **`frontend/src/pages/Step1Script.tsx`**
  - Voiceover upload dropzone (full width, 200px height, drag-and-drop + click)
  - Progress bar during upload (amber fill)
  - Transcript display (scrollable 600px area, `body-md` Source Sans 3)
  - Original Script input (collapsible textarea with monospace font)
  - AI Diff UI — side-by-side diff view (GitHub-style) with word-level LCS algorithm
  - Changes highlighted in `success` green (#22C55E) and `error` red (#EF4444)
  - Approve/Reject buttons per change block
  - Error handling with retry banner

#### Frontend — Step 5 Video Page
- **`frontend/src/pages/Step5Video.tsx`**
  - Effect selection grid — per-segment dropdown with 7 options
  - Auto-assign — random effect assignment on first load (excluding adjacent duplicates)
  - Randomize button (ghost, Shuffle icon) — re-assigns all effects
  - Burn captions checkbox (unchecked by default)
  - Download SRT button (ghost, Download icon)
  - Generate Video button (amber primary, disabled if images missing)
  - Progress bar (full-width amber bar, "Processing segment N of M...")
  - Download Video button (appears after generation)
  - Console output panel (collapsible, `mono-sm`, `surface-dim` background, auto-scroll)

#### Frontend — Wizard Navigation Completion
- **`frontend/src/components/WizardShell.tsx`**
  - Added `useNavigate` + `useParams` for React Router navigation
  - Step completion enforcement — Next button disabled until current step is complete
  - Step 1 and Step 5 rendering in `renderStepContent()` switch/case
  - `handleBack`/`handleNext` navigate to `/project/:uuid/step/{N}`
  - Fetches project state from `GET /api/v1/projects/{uuid}/state`

- **`frontend/src/components/Stepper.tsx`**
  - Step completion colors: completed = teal (#06B6D4), current = amber (#F0A040), pending = dim (#5A5A6A)
  - Step click disabled for incomplete steps (prevents skipping ahead)

#### Testing
- **Backend Tests:** `test_video.py` (45 tests)
  - Video endpoints: generate, status, download, SRT (happy path + error cases)
  - Segment effects: update, invalid, not found, out of bounds
  - Effects service: all 6 effects, random assign, zoompan filter generation
  - FFmpeg service: all 7 effects, concat, mix, burn, orchestrator
  - All mocked with `unittest.mock.patch` for subprocess

- **Frontend Tests:** `step1.spec.ts` (7 tests), `step5.spec.ts` (10 tests)
  - Step 1: dropzone, transcript, diff UI, Next button disabled/enabled, error retry, border-radius, fonts
  - Step 5: effect grid, randomize, burn captions, generate disabled/enabled, progress bar, download, console, error, border-radius, fonts

### Changed
- **Frontend build config** — `vite.config.ts` added `resolve.alias` for `@/lib/utils` path resolution
- **Backend tests** — Total: 96 tests (up from 51 in Session 2)
- **Frontend tests** — Total: 52 tests (up from 34 in Session 2)

### Fixed
- **Vite path alias** — `@/lib/utils` import failed in dev server; fixed by adding alias to `vite.config.ts`
- **SRT path consistency** — `services/srt.py` now uses `PROJECTS_BASE_DIR` matching other routers

### Known Issues
- ~~**ffmpeg version** — 4.0 (older than recommended 6.x+ but functional; zoompan validated)~~ **Resolved** — Upgraded to 8.1.1
- **OpenAI API key** — Validated working (billing added during Session 2)
- **lucide-react** — Removed from `package.json`; `components.json` updated to `@phosphor-icons/react`

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

### Session 3 (2026-06-04) — Video Generation + Step 1 Frontend
**Goal:** Step 5 video generation (ffmpeg pipeline), Step 1 frontend (voiceover upload + transcription + diff UI), caption burning, SRT download, complete wizard navigation.
**Status:** ✅ COMPLETE — 17 tasks, 3 waves, 4-phase verification passed.
**Deliverables:** ffmpeg pipeline service, motion effects logic, video generation/status/download/SRT endpoints, Step 1 and Step 5 frontend pages, wizard navigation completion, 96 backend tests + 52 frontend tests.

### Session 4 (2026-06-04) — Polish
**Goal:** UI refinements, cascade warning UI, accessibility audit (WCAG 2.1 AA), end-to-end integration testing (full wizard flow).
**Status:** ✅ COMPLETE — 12 tasks, 3 waves, 4-phase verification passed.
**Deliverables:** Accessibility attributes across all 5 steps, `useFocusTrap` hook, `SkeletonTable`/`AmberBar` loading components, ghost button transparency fix, E2E happy path + error path + accessibility gap tests, mock test backend, 102 backend tests + 75 frontend tests.

---

## File Inventory

### Backend (25 Python files)
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
backend/routers/video.py
backend/services/__init__.py
backend/services/fireworks.py
backend/services/whisper.py
backend/services/chunking.py
backend/services/srt.py
backend/services/state.py
backend/services/ffmpeg.py
backend/services/effects.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/test_projects.py
backend/tests/test_characters.py
backend/tests/test_segments.py
backend/tests/test_images.py
backend/tests/test_fireworks.py
backend/tests/test_video.py
backend/utils/__init__.py
```

### Frontend (16 TSX files + 10 test files)
```
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/components/WizardShell.tsx
frontend/src/components/Stepper.tsx
frontend/src/components/ui/button.tsx
frontend/src/components/AmberBar.tsx
frontend/src/components/SkeletonTable.tsx
frontend/src/hooks/useFocusTrap.ts
frontend/src/pages/Dashboard.tsx
frontend/src/pages/Step1Script.tsx
frontend/src/pages/Step2Characters.tsx
frontend/src/pages/Step3Segments.tsx
frontend/src/pages/Step4Images.tsx
frontend/src/pages/Step5Video.tsx
frontend/src/styles/theme.css
frontend/src/styles/index.css
frontend/tests/dashboard.spec.ts
frontend/tests/wizard.spec.ts
frontend/tests/step1.spec.ts
frontend/tests/step2.spec.ts
frontend/tests/step3.spec.ts
frontend/tests/step4.spec.ts
frontend/tests/step5.spec.ts
frontend/tests/accessibility-gaps.spec.ts
frontend/tests/e2e-error-paths.spec.ts
frontend/tests/e2e-happy-path.spec.ts
frontend/tests/global-setup.ts
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
| Session 3 | 96 | 52 | 148 |
| Session 4 | 102 | 75 | 177 |

### Backend Test Breakdown
- `test_fireworks.py` — 9 tests (client, base_url, retry logic, json_schema, error handling)
- `test_characters.py` — 8 tests (extract, prompts, missing script, prerequisite, failures, update)
- `test_segments.py` — 14 tests (breakdown, prompts, split, merge, missing files, prerequisite, failures, batch fallback)
- `test_images.py` — 9 tests (upload, non-PNG, wrong ratio, RGBA, low resolution, GET, not found)
- `test_projects.py` — 11 tests (CRUD, cascade, state machine, Whisper mock, not found, transcript)
- `test_video.py` — 45 tests (generate, status, download, SRT, effects, ffmpeg mocks, zoompan filters)

### Frontend Test Breakdown
- `dashboard.spec.ts` — 5 tests (empty state, Create Project button, project card, fonts, background)
- `wizard.spec.ts` — 9 tests (heading, stepper, colors, border-radius, fonts, background)
- `step2.spec.ts` — 5 tests (extract button, table rows, edit, copy, JSON toggle)
- `step3.spec.ts` — 8 tests (generate button, table rows, editable prompts, split/merge, error, prompts button, radius, font)
- `step4.spec.ts` — 7 tests (grid cells, upload button, details button, placeholder, thumbnail, details modal, upload flow)
- `step1.spec.ts` — 7 tests (dropzone, transcript, diff UI, Next button disabled/enabled, error retry, radius, font)
- `step5.spec.ts` — 10 tests (effect grid, randomize, burn captions, generate disabled/enabled, progress bar, download, console, error, radius, font)
- `accessibility-gaps.spec.ts` — 14 tests (role="alert", aria-live, aria-expanded, aria-controls, aria-label, aria-current, aria-modal, focus trap, keyboard accessibility, progress bar ARIA, total alert count, total expanded count)
- `e2e-error-paths.spec.ts` — 2 tests (corrupted voiceover upload, cascade invalidation preserves images)
- `e2e-happy-path.spec.ts` — 7 tests (create project, upload voiceover, extract characters, generate segments, upload images, generate video, verify output files)

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
- `GET /api/v1/projects/{uuid}/characters` — Get character list
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

### Video
- `POST /api/v1/projects/{uuid}/video/generate` — Generate video from segments
- `GET /api/v1/projects/{uuid}/video/status` — Get video generation status
- `GET /api/v1/projects/{uuid}/video/download` — Download generated MP4
- `GET /api/v1/projects/{uuid}/video/srt` — Download captions.srt
- `GET /api/v1/projects/{uuid}/video/ass` — Download captions.ass

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
