# Changelog

All notable changes to the Conduit project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] — 2026-06-12 — Character Pipeline Resilience

### Fixed
- **Resilient name matching for character prompts** (`backend/routers/characters.py`) — Introduced `_normalize_name` (casefold, trim, collapse whitespace, strip leading `"the "`, strip punctuation) for matching AI output names back to input names. Positional fallback when input/output counts match but normalized names still drift. Replaces the previous exact-name join that 502'd on any paraphrase.
- **Graceful timeline guards** (`backend/routers/characters.py`) — AI quirks that previously 502'd now degrade gracefully with logged warnings:
  - **Duplicate names** → disambiguated by appending version label/index.
  - **Missing persons** → backfilled as a single default version using the original extraction description.
  - **Inconsistent `identity_anchor`** → coalesced to the first non-empty anchor per `base_name`.
- **Re-run invalidation** (`backend/routers/characters.py`, `backend/services/state.py`) — `extract_characters` and `generate_character_timeline` both call `invalidate_downstream(2)` before setting their own completed flags, so re-running either step resets downstream state (Steps 3–5) and deletes orphaned `segments.json`. `_clear_sub_step_state(2)` now also clears `step_2_timeline_complete`, so re-extract/PUT fully resets the Step 2 sub-state.

### Changed
- **Impostor↔original appearance inheritance** (`backend/services/prompts.py`) — Extraction prompt now instructs the AI: impostors, doppelgängers, and disguised entities must inherit the mimicked character's stable surface appearance (hair, build, base clothing) and layer only the described corruption on top, keeping both entities distinct. Front profile and turnaround "Version consistency rules" carry the same guidance for creature/NPC types that mimic humans.

### Testing
- 225 backend tests passed (0 failures); `tsc --noEmit` → 0 errors. Rewrote 3 `test_character_timeline.py` guard tests from 502 assertions to graceful-degradation assertions (`test_timeline_duplicate_name_disambiguated`, `test_timeline_missing_person_backfilled`, `test_timeline_inconsistent_anchor_coalesced`). Added 4 new `test_characters.py` tests: `test_generate_prompts_name_drift_resolved` (normalized-name + positional fallback), `test_extract_invalidates_downstream`, `test_timeline_invalidates_downstream`, and `test_normalize_name_conservative`. `test_characters.py` now has 32 tests.

## [0.8.9] — 2026-06-11 — Segment-Prompts Always-Batch + Per-Batch Persistence

### Fixed
- **Segment prompts now always generate in small batches** (`backend/routers/segments.py`) — the previous primary path sent all segments in a single AI call, which timed out on slow providers (e.g. umans) for projects with >25 segments. The endpoint now always batches via `_generate_and_persist_prompts`, using tunable `batch_size` (default 12) and `overlap` (default 5). Segments are merged and persisted to `segments.json` after every batch, so a mid-run timeout leaves partial progress on disk.
- **Resume on retry** — the driver only regenerates segments lacking a non-empty `segment_prompt`. Re-running the endpoint after a 504 resumes where the prior call left off, without redundant AI calls for completed batches.
- **Guarded state advance** — `step_3_complete` / `step_3_pass_2_complete` are only set when `all(s.get("segment_prompt") for s in segments)`. If any segment is still empty (e.g., a batch failed or was omitted), the project stays at `step_2_complete` and the wizard correctly shows Step 3 as incomplete.
- **Env-tunable batch knobs** (`backend/.env.example`) — `CONDUIT_SEGMENT_BATCH_SIZE` and `CONDUIT_SEGMENT_BATCH_OVERLAP` override the defaults (12 / 5). `max(1, …)` and `min(…, batch_size-1)` guards prevent zero or oversized overlap.
- **Removed dead token-limit fallback path** — `_generate_prompts_in_batches` and `_is_token_limit_error` are deleted. The batching path was previously reachable only after a 413/Context-length error; it is now the primary path.

### Testing
- 221 backend tests passed (0 failures); `tsc --noEmit` → 0 errors. Rewrote `test_segments.py` batch-fallback test into `test_generate_prompts_always_batches` (+ overlap-win assertion), removed the obsolete truncation-fallback test, aligned `missing_segment_index_resilience` with the new state-advance guard, and added 4 new tests: `partial_progress_persisted_on_timeout`, `resume_skips_completed`, `small_project_single_batch`, `idempotent_when_all_complete`. `test_segments.py` now has 46 tests.

## [0.8.8] — 2026-06-11 — AI Timeout Sizing + 504 Mapping

### Fixed
- **AI client timeout is now env-configurable** (`FIREWORKS_TIMEOUT`, default 300s) — umans is materially slower than Fireworks and was tripping the old hardcoded 120s cap; `max_retries=0` stops the SDK from severing a slow-but-progressing request at the timeout and retrying; the redundant 60s/120s stack is unified to one configurable value (+ small asyncio safety buffer); AI timeouts now return a clean **504** (was an unhandled 500) across all Fireworks-backed endpoints.

### Testing
- 218 backend tests passed (0 failures); `tsc --noEmit` → 0 errors. Added 2 `test_fireworks.py` tests (timeout env override + timeout normalization) and 1 `test_characters.py` test (504 on timeout).

## [0.8.7] — 2026-06-11 — Prompt JSON-Contract + Step 4 Hardening

### Fixed
- **AI prompts now pin their JSON output shape in prose** (`backend/services/prompts.py`) — umans-coder (and potentially other non-Fireworks providers) ignores the `response_format.schema` hint and returns free-form JSON. All four at-risk builders now explicitly state the top-level key in text:
  - **Extraction** — `Return ONLY a JSON object with a top-level "characters" array` (was primed with "entities", causing `{"entities":...}` → 502).
  - **Breakdown** — `Output a JSON object with a top-level "segments" array` (was ambiguous "JSON array of segments").
  - **Front profile** — `Return ONLY a JSON object with a top-level "characters" array; each element has fields: name, front_profile_prompt`.
  - **Turnaround** — same pattern with `turnaround_prompt`.
  - **Pass-2 (segment prompts)** — already had the `"segments"` wrapper; added `Every output item MUST include segment_index` emphasis since Pass-2 result-map matching keys on that field.
- **Pass-2 tolerates missing `segment_index`** (`backend/routers/segments.py`) — defensive comprehension skips items without `segment_index` instead of raising an unhandled `KeyError` → 500. Segments absent from the map keep empty `segment_prompt`/`characters_present`.
- **Step 4 PUT response is now checked** (`frontend/src/pages/Step4Images.tsx`) — captures the `PUT /step/4` response; warns on non-ok but still refreshes state. Prevents silent assumption of success when prerequisites are unmet.
- **Invalidation clears stale video state and output file** (`backend/services/state.py`) — when a project is invalidated at/through Step 4, `video_progress` and `video_error` are dropped from `state.json` and `output/output.mp4` is deleted if present. Previously, re-uploading images at `step_5_complete` left the old video reporting "completed".

### Testing
- 215 backend tests passed (0 failures); `tsc --noEmit` → 0 errors. Added 5 prompt-contract assertions + 1 invalidation video-cleanup test + 1 Pass-2 missing-segment-index resilience test.

## [0.8.6] — 2026-06-11 — umans Provider + Step 2–4 Next Refresh

### Changed
- **AI provider is now fully env-configurable** (`backend/services/fireworks.py`, `backend/.env.example`) — added `FIREWORKS_MODEL` env override so the model identifier can be swapped per-deployment. Defaults remain the Fireworks Kimi router (`accounts/fireworks/routers/kimi-k2p6-turbo`). To use the umans Code Pro Plan, set `FIREWORKS_BASE_URL=https://api.code.umans.ai/v1`, `FIREWORKS_MODEL=umans-coder`, and `FIREWORKS_API_KEY=<umans key>`. Whisper transcription stays on OpenAI (`OPENAI_API_KEY`) unchanged.

### Fixed
- **"Next" button now enables immediately after Steps 2–4 complete** (`frontend/src/components/WizardShell.tsx`, `frontend/src/pages/Step{2,3,4}.tsx`) — `WizardShell` now exposes `refreshProjectState()` and passes it to Steps 2/3/4 as an optional `onStateChange` callback. On successful state-advancing POSTs (Step 2 prompts, Step 3 prompts), the callback refreshes `projectState` so `canGoNext` evaluates to `true` without a page reload. Step 4 additionally calls `PUT /step/4` once the final image is uploaded, advancing `step_3_complete → step_4_complete` so Step 5 generation is reachable. A step-change refetch is also added as a safety net.

### Security Note
- The AI key lives only in `.env` (gitignored). If it was shared, rotate it.

### Testing
- 208 backend tests passed (0 failures); `tsc --noEmit` → 0 errors. Added 1 regression test asserting `FIREWORKS_MODEL` env override (set/unset).

## [0.8.5] — 2026-06-10 — Hardening (Code-Review Fixes)

### Fixed
- **Video generation crash from a bad `datetime` import** (`backend/services/ffmpeg.py`) — `_write_progress` called `datetime.now(timezone.utc)` while the module did `import datetime` (no `timezone`), raising at runtime after the first segment rendered. Switched to `from datetime import datetime, timezone`. (Masked previously because video tests mocked the pipeline.)
- **Chunked transcription rewound timestamps for >25 MB audio** (`backend/services/chunking.py`, `backend/routers/projects.py`) — `chunk_audio` now returns `(chunk_path, start_offset_seconds)` tuples and the upload pipeline adds each chunk's original-audio offset to every word's `start`/`end`, so captions and segment timing stay on the absolute timeline (no rewind). The <25 MB single-chunk path is unchanged (offset `0.0`).
- **`GET /characters` stripped generated prompts** (`backend/routers/characters.py`) — the endpoint returned via `response_model=CharacterList`, which dropped `front_profile_prompt`/`turnaround_prompt` (not declared on `CharacterDescription`), so Step 2 prompt cards vanished on reload. Now returns the raw dict (mirrors the 0.8.1 `get_segments` fix) while still normalizing version-field defaults for legacy files. PUT behavior is unchanged (prompts regenerate via `invalidate_downstream(2)`).
- **Non-mp3 voiceovers 404'd at video generation** (`backend/routers/video.py`) — upload accepts `.mp3/.wav/.m4a` but generation hardcoded `voiceover.mp3`. Generation now resolves the voiceover across all three extensions.
- **Video status reported 0 segments** (`backend/routers/video.py`) — `get_video_status` read `segments.json` from the project root, but the canonical location is `.conduit/segments.json`. Now resolves `.conduit/` first (root fallback), so the progress UI shows the real segment count.
- **Standardized error response shape** (`backend/main.py`) — the global 500 handler returned `{"error": ...}` while every `HTTPException` returns `{"detail": ...}`; unified to `{"detail": ...}` (the frontend already reads `.detail`).
- **Misleading upload status wording** (`backend/routers/projects.py`) — voiceover upload transcribes synchronously, so the response now reports `processing: false` / "Audio uploaded and transcribed." (was "Transcription in progress").

### Maintenance
- **ffmpeg path is now configurable** (`backend/services/ffmpeg.py`, `backend/.env.example`) — removed the hardcoded machine-specific path; `FFMPEG_PATH` reads `CONDUIT_FFMPEG_PATH` (default `ffmpeg` on PATH). **Local deployments must set `CONDUIT_FFMPEG_PATH` in `.env` if ffmpeg is not on PATH.**
- **Removed the `_burn_captions_impl` alias** (`backend/services/ffmpeg.py`) — `generate_video`'s `burn_captions` parameter was renamed to `should_burn_captions`, so it no longer shadows the `burn_captions` function.
- **Documented deliberate decisions** — synchronous inline video render (single-user localhost) and the `schema_version` forward-compat placeholder; corrected `random_assign_effects` and `generate_srt` docstrings to match behavior.

### Testing
- 207 backend tests passed (0 failures); `tsc --noEmit` → 0 errors. Added 8 regression tests (write-progress timestamp, chunk offsets, GET-characters prompt preservation + legacy backfill, .wav voiceover resolution, video-status count, ffmpeg-path env, error-shape).

## [0.8.4] — 2026-06-09 — Character Prompt Truncation Fix

### Fixed
- **Step 2 "Generate Prompts" 502 on truncation — character AI calls were under-budgeted at 2048 tokens** (`backend/routers/characters.py`) — All four `chat_completion` calls (Call 1 extraction, timeline version detection, and Call 2 front-profile + turnaround prompts) omitted `max_tokens` and fell back to the 2048 default. For projects with a versioned/large cast, the turnaround prompt JSON exceeded 2048 tokens and truncated mid-string (`Unterminated string ... char 8823/9598`), which the 0.8.1 JSON guard correctly surfaced as a clean 502. Introduced `CHARACTER_PROMPTS_MAX_TOKENS = 16000` and applied it to all four calls, mirroring the `BREAKDOWN_MAX_TOKENS` (0.8.1) and `SEGMENT_PROMPTS_MAX_TOKENS` (0.8.3) fixes in `segments.py`. Unlike the segment passes, character prompt generation has no overlapping-batch fallback, so the token-budget bump is the sole remedy. `DEFAULT_MAX_TOKENS` (2048) in `fireworks.py`, the JSON guard, and `_handle_fireworks_error` are unchanged.

### Testing
- 199 backend tests passed (0 failures); `tsc --noEmit` → 0 errors. Added 3 regression tests asserting `max_tokens=16000` on the extract, timeline, and both Call-2 (front + turnaround) requests.

## [0.8.3] — 2026-06-08 — Stable Segment IDs + Step 3 Fixes

### Fixed
- **Stable `segment_id` decouples images from mutable segment index** (`backend/models/segments.py`, `backend/routers/segments.py`, `backend/routers/images.py`) — Every segment now carries a unique `segment_id` (UUID). Images are stored as `images/{segment_id}.png` and resolved server-side from the index-addressed API. Split/merge no longer misaligns Step 4 thumbnails or Step 5 video frames.
- **Lazy migration for legacy projects** (`backend/routers/images.py`) — `get_images_status` and `upload_image` automatically stamp missing `segment_id`s and rename legacy `images/{index:04d}.png` files. Idempotent: no-op once all ids exist.
- **Step 3 duplicate "Generate Segments" CTA** (`frontend/src/pages/Step3Segments.tsx`) — Top-row button is now gated on `segments.length > 0`, so the empty state shows exactly one CTA (the inline one) and the non-empty state shows the top-row re-run affordance.
- **Pass 2 prompt-generation truncation 502** (`backend/routers/segments.py`) — `max_tokens` bumped from 4096 to 16000 (same as Pass 1). The `_is_token_limit_error` keyword list now includes `"truncated"`, so truncation errors trigger the overlapping-batch fallback instead of an immediate 502.

### Known Limitation
- Projects that were already desynced by a pre-0.8.3 split/merge (image files misaligned with segments) cannot be perfectly recovered by the migration — the legacy file renames match the current segment index, but the pre-existing desync may have already moved files to the wrong segment.

### Testing
- 196 backend tests passed (0 failures); `tsc --noEmit` → 0 errors.

## [0.8.2] — 2026-06-08 — Split/Merge Prompt Preservation

### Fixed
- **`split_segment` and `merge_segment` no longer silently wipe `segment_prompt`, `characters_present`, and `image_path` from untouched segments** (`backend/routers/segments.py`) — Both endpoints now operate on raw dicts (mirroring the 0.8.1 `update_segments`/`get_segments` fix). Untouched segments retain all optional fields. Changed segments (split halves / merged result) are reset with `segment_prompt=""`, `characters_present=[]`, and `image_path` removed for regeneration.

### Known Limitation
- ~~Images are stored as `images/{segment_index:04d}.png` and split/merge renumber indices, so existing image files can misalign with segments after re-segmentation — deferred to future work.~~ **Resolved in 0.8.3** — stable `segment_id` decouples images from mutable segment index.

### Testing
- 183 backend tests passed (0 failures); `tsc --noEmit` → 0 errors.

## [0.8.1] — 2026-06-08 — Post-Release Fixes

### Fixed
- **Breakdown truncation / 500** (`backend/routers/segments.py`, `backend/services/fireworks.py`) — Pass 1 breakdown now uses `max_tokens=16000` (up from default) to prevent mid-segment truncation. Centralized JSON-parse guard in `fireworks.py` catches malformed AI responses with `try/except json.JSONDecodeError`, re-raising as `APIError` so callers map it to 502 instead of leaking a 500.
- **PUT prompt preservation** (`backend/routers/segments.py`) — `PUT /segments` now merges incoming fields with on-disk data (`{**on_disk[idx], **incoming[idx]}`) so `segment_prompt`, `characters_present`, and `image_path` are preserved when the client omits them.
- **Step 3 prompt visibility** (`backend/routers/segments.py`, `frontend/src/pages/Step3Segments.tsx`) — `GET /segments` no longer strips optional fields via `response_model=Segments`; returns raw dicts so `segment_prompt`, `characters_present`, and `image_path` are always present. Frontend aligned field names from legacy `prompt`/`characters` to `segment_prompt`/`characters_present`.
- **Title bar project name** (`frontend/src/components/WizardShell.tsx`) — Fetches `GET /projects/{uuid}` and displays the real project name in the title bar instead of hardcoded `Untitled Project`.

### Changed
- **Step 2 / Step 3 UI polish** (`frontend/src/pages/Step2Characters.tsx`, `frontend/src/pages/Step3Segments.tsx`) — Step 2: description textarea is now vertically resizable (`resize-y`, 4 rows), single-default-version groups render a compact row instead of a full card, `appears_from` placeholder changed to a narrative hint, AI model label corrected to `Fireworks · Kimi K2.6`. Step 3: action buttons right-aligned (`justify-end`) with secondary-on-left / primary-on-right ordering, empty state shows an inline primary CTA.

### Maintenance
- **Synced `requirements.txt` to the installed/tested versions** — pins had drifted behind the environment. Bumped `fastapi` 0.115.0→0.119.1, `uvicorn` 0.34.0→0.47.0, `pydantic` 2.10.0→2.13.4, `python-multipart` 0.0.20→0.0.28, `openai` 1.60.0→2.38.0, `httpx` 0.28.0→0.28.1, `pytest` 8.3.0→9.0.3, `pytest-asyncio` 0.24.0→1.3.0, `respx` 0.22.0→0.23.1, `python-dotenv` 1.0.0→1.2.2 (pydub/srt/aiosqlite unchanged). Tech Stack appendix updated to match. The `APIError(message, request, *, body)` signature used by the breakdown JSON-guard is stable across openai 1.x/2.x.

### Testing
- 181 backend tests passed (0 failures); `tsc --noEmit` → 0 errors.

## [0.8.0] — 2026-06-08 — Character Versions

### Added
- **Character versions with timeline pass** (`backend/routers/characters.py`) — New `POST /api/v1/projects/{uuid}/characters/timeline` endpoint. Detects per-character versions (e.g., "Alice (young)", "Alice (old)") from the script. Adds `base_name`, `version_label`, `version_index`, `appears_from`, and `identity_anchor` fields. Guards: duplicate names → 502, missing persons → 502, inconsistent `identity_anchor` per `base_name` → 502. Persists to `characters.json` and sets `step_2_timeline_complete` sub-step state.
- **Identity anchoring** (`backend/models/characters.py`, `backend/services/prompts.py`) — `identity_anchor` is duplicated across all versions of the same `base_name` to keep generated images consistent. Call 2 (front profile + turnaround) prompt builders inject `identity_anchor` and `version_label` into the system prompt for each version.
- **Per-segment character resolution + override** (`backend/routers/segments.py`) — Pass 2 resolves which version of each character appears in each segment based on `appears_from` timestamps. `characters_present` stores versioned names (e.g., `Alice (young)`). Flashback / non-monotonic timeline support: if a segment's time is before a version's `appears_from`, it resolves to the earliest version.
- **Single-segment prompt regeneration** (`backend/routers/segments.py`) — New `POST /api/v1/projects/{uuid}/segments/{segment_index}/prompt` endpoint. Accepts optional `character_versions` dict to pin specific versions for the segment. Updates only the target segment's `segment_prompt` and `characters_present` without touching others.
- **Version-management UI** (`frontend/src/pages/Step2Characters.tsx`) — Timeline pass button, version list display, `identity_anchor` preview, and per-version prompt cards.
- **Per-segment override UI** (`frontend/src/pages/Step3Segments.tsx`) — Regenerate button per segment with version override dropdown. Shows `characters_present` as versioned badges.

### Changed
- **Pass 2 Rule 9 (within-version consistency)** (`backend/services/prompts.py`) — Updated segment prompt system prompt to require that consecutive segments featuring the same character version must keep visual details consistent (clothing, age expression, props) unless the script explicitly describes a change.
- **Character-edit invalidation** (`backend/routers/characters.py`, `backend/services/state.py`) — `PUT /api/v1/projects/{uuid}/characters` calls `invalidate_downstream(2)`, resetting the project to `step_1_complete` and clearing `step_2_call_2_complete` plus all Step 3–4 sub-steps (forcing Call 2 + segments to re-run). Deletes `segments.json` when characters are edited. Previously edits did not invalidate downstream segments, causing stale prompts.

### Fixed
- **Backward-compatible schema loading for pre-version `characters.json`** (`backend/models/characters.py`) — Projects with legacy `characters.json` (lacking `base_name`, `version_label`, `version_index`, `identity_anchor`, `appears_from`, `front_profile_prompt`, `turnaround_prompt`) load without `ValidationError`. Missing fields default to: `base_name` = `name`, `version_label` = `"default"`, `version_index` = `0`, `identity_anchor` = `""`, `appears_from` = `""`, prompts = `""`. Call 2 and GET endpoints both normalize on read.

### Testing
- 172 backend tests passed (0 failures); `tsc --noEmit` → 0 errors.

## [0.7.3] — 2026-06-08 — Test Isolation + Delete Atomicity

### Fixed
- **Centralized + guarded test `PROJECTS_BASE_DIR` patching** (`backend/tests/isolation_modules.py`, `conftest.py`) — Created a single `PATCHED_MODULES` tuple covering all 7 base-dir modules (`routers.projects`, `services.state`, `routers.segments`, `services.srt`, `routers.images`, `routers.video`, `services.ffmpeg`). `conftest.py` now loops over this tuple to patch and restore, with an in-fixture assertion that fails loudly if any module is not patched. This closes the root cause of orphaned project folders accumulating from test leaks.
- **`delete_project` now removes files before the DB row** (`backend/routers/projects.py`) — Reordered: verify project exists (SELECT → 404) → `shutil.rmtree` (guarded, 500 on failure, row + folder intact) → DELETE row → 204. A failed `rmtree` can no longer orphan a folder. Removed redundant local `import shutil`.

### Added
- **Meta-test guarding against unpatched modules** (`backend/tests/test_isolation.py`) — Introspects `routers` and `services` packages, imports every submodule, and asserts any module defining `PROJECTS_BASE_DIR` is present in `PATCHED_MODULES`. Fails with a clear message naming the unpatched module. Would have caught the `services.ffmpeg` leak immediately.
- **Delete atomicity tests** (`backend/tests/test_projects.py`) — Replaced the weak `test_delete_project` with three tests:
  - `test_delete_project_removes_folder_and_row` — asserts both DB row and filesystem folder are removed
  - `test_delete_project_rmtree_failure_no_orphan` — monkeypatches `shutil.rmtree` to raise; asserts 500 response and both row + folder survive (retryable)
  - `test_delete_project_not_found` — DELETE non-existent UUID returns 404

### Maintenance
- Removed 10 orphaned project folders (`projects/` directory) that accumulated from prior test leaks. `be3bc4c8` (live project) and `test-setup`/`test-status` preserved.

### Testing
- 154 backend tests passed (0 failures); `tsc --noEmit` → 0 errors.

## [0.7.2] — 2026-06-07 — Re-upload Invalidation Fix

### Fixed
- Fixed voiceover re-upload deleting freshly-generated `captions.srt` by invalidating downstream BEFORE re-transcription. Previously the invalidation ran after the new files were written, causing the SRT to be immediately deleted — breaking caption download and burn.
- Removed dead duplicate root `words.json` (canonical copy now lives only at `.conduit/words.json`). No reader ever accessed the root copy.

### Added
- Real `/voiceover` re-upload regression test: asserts `captions.srt` survives a second upload while `.conduit/segments.json` is correctly cleared.
- Direct `invalidate_downstream(1)` test documenting the standalone Step 1 deletion semantics.

### Testing
- 151 backend tests passed (0 failures); `tsc --noEmit` → 0 errors. Frontend: no code changes this release; Playwright suite not re-run (last recorded 73 specs at v0.6.0).

## [0.7.1] — 2026-06-07 — Post-0.7.0 Deviation Fixes

### Fixed
- **`segments.py` now reads `characters.json` from the project root** (`backend/routers/segments.py:416`) — Fixes silent loss of character context in segment prompts. The writer (`characters.py`) always saved to the project root, but the reader was looking in `.conduit/`, causing Pass 2 to build prompts with empty character data. Hardened regression test (`test_generate_prompts_success`) asserts the request body contains `"Alice"`.
- **Removed unfilled `{character_profiles}` block** from the Pass 2 system prompt (`backend/services/prompts.py`) — The placeholder was never hydrated, so the AI received a literal template string. Deleted the paragraph and updated `test_prompts.py` assertions to verify its absence.
- **Synced `frontend/package.json` to 0.7.0** (`frontend/package.json`) — Version drifted to `0.6.0` after the `[0.7.0]` release tag.
- **Migrated `main.py` to a FastAPI lifespan handler** (`backend/main.py`) — Replaced deprecated `@app.on_event("startup")` with `@asynccontextmanager async def lifespan(...)`. Eliminates the `on_event` DeprecationWarning; startup order (`init_db()` → `OPENAI_API_KEY` check) unchanged.
- **Corrected AGENTS.md Data Files diagram** — Updated the `.conduit/` layout to reflect real backend paths: `project.json`, `state.json`, `source_of_truth_script.txt`, `words.json`, `segments.json` live under `.conduit/`; `characters.json`, `images/`, `output/`, voiceover, transcripts, and captions live at the project root. Added `transcript.json` to root (was missing). Noted `words.json` is mirrored in `.conduit/`.

### Testing
- **Backend tests:** 149 backend tests passed (up from 148, +1 from `test_prompts.py` no-placeholder assertion).
- **Frontend:** `npx tsc --noEmit` → 0 errors.

---

## [0.7.0] — 2026-06-07 — Prompt Accuracy Fix + Style Abstraction

### Prompt Accuracy
- **All four AI prompts rewritten to match `DESIGN_SPEC.md`** (`backend/services/prompts.py`) — Replaced bare-bones stubs with spec-compliant system prompts:
  - **Call 1 (character extraction)** — §4.1: "character extraction engine" role, `speaking|creature|npc_entity` type enum, `major|minor` importance enum, detailed-visual-infer-if-blank description rule, `<system>`+`<script>` XML split.
  - **Call 2 (character prompts)** — §4.2: Two batch calls (front profile + turnaround) with verbatim style anchors from "Secret Level / Love Death and Robots" style, merge-by-name guard, 2–4 line comma-separated rule, no anime/cel-shading prohibition.
  - **Pass 1 (segment breakdown)** — §5.2: "video editor" role, 8 explicit break rules (visual beats, sentence merging, scene transitions, pause ≥1.5s, 3–10s target duration), `<system>`+`<script>`+`<word_timestamps>` XML split.
  - **Pass 2 (segment prompts)** — §5.2: "scene director" role, 9 prompt construction rules (style anchor, scene description, character placement, camera/framing, color palette, negative constraints, 3–6 line length, `@Name` references, cross-segment consistency), good/bad examples, shot-type vocabulary.
- **No "helpful assistant" in production code** — All system messages now have specific AI roles (extraction engine, art prompt writer, video editor, scene director).
- **No legacy enums** — `protagonist/antagonist/supporting/main` removed from all prompt and schema code.

### Style Abstraction
- **`StyleProfile` registry** (`backend/services/prompts.py`) — `@dataclass(frozen=True)` with fields: `id`, `display_name`, `art_role_phrase`, `front_profile_anchor`, `turnaround_anchor`, `segment_scene_anchor`, `prohibitions`, `negative_style_example`. Seeded with ONE entry `"secret_level"`.
- **`STYLES` dict + `get_style()`** — Lookup by `style_id` with fallback to `DEFAULT_STYLE_ID` ("secret_level"). Adding a new style = one registry entry.
- **`SHOT_TYPES` vocabulary** — 12 shot types: extreme wide, wide, medium, close-up, extreme close-up, over-the-shoulder, Dutch angle, bird's eye, worm's eye, POV, establishing shot, aerial/drone. Referenced in Pass 2 system prompt as prose guidance (not structured field).
- **`style_id` persistence** — `get_style_id(uuid)` reads `state.json` (default "secret_level"). Backward-compatible for existing projects without key.

### Architecture
- **`backend/models/characters.py`** — New `CharacterDescription`, `CharacterList`, `CharacterPrompts`, `CharacterPromptsList`, `FrontProfilePromptList`, `TurnaroundPromptList` with `Literal` enum enforcement.
- **`backend/models/segments.py`** — New `SegmentBreakdown`, `Segments`, `SegmentPrompt`, `SegmentPrompts`, `SplitRequest`, `SegmentEffectUpdate` (moved from routers).
- **`backend/services/prompts.py`** — Central home for all 4 prompt texts. 5 message builders returning `list[dict]` system+user messages. No import from `models/` or `routers/` (cycle-free).
- **`validate-before-persist` guard** — `CharacterList(**result)` is parsed BEFORE writing `characters.json`. `ValidationError` → `HTTPException(502, "AI returned data in an unexpected format")` (generic, no `str(exc)` leak).
- **`_handle_fireworks_error` preserved** — Existing error mapping (AuthError→502, RateLimit→429, APIError→502) unchanged.

### Frontend
- **Enum alignment** (`frontend/src/pages/Step2Characters.tsx`) — `type` enum updated to `speaking|creature|npc_entity`, `importance` to `major|minor`. Badge conditionals fixed.
- **Field rename** — `turnaround_reference_prompt` → `turnaround_prompt` (pre-existing bug where backend wrote `turnaround_prompt` but frontend read the wrong field name).

### Testing
- **Backend tests:** 148 backend tests passed (up from 114 at 0.6.0): +28 `test_prompts`, +2 `test_schema_flatten`, +2 `test_style_state`, plus `test_characters` 8→16 and `test_segments` 14→18.
- **Frontend:** `npx tsc --noEmit` → 0 errors.
- **Greps verified:** no "helpful assistant", no legacy enums, no schemas in routers.

### Guardrails Honored
- No style selector UI, no anime/other styles, no `shot_type` structured field, no SQLite migration, no batch-fallback strategy change.

---

## [0.6.1] — 2026-06-06 — Follow-up Fixes

### Security
- **Fix exception leak in `images.py`** (`backend/routers/images.py:89`) — Replaced `detail=f"Invalid image file: {exc}"` with generic `detail="Invalid image file — please upload a valid PNG"`. Added `logging.error("Image validation failed", exc_info=exc)` for full server-side logging. This was the last remaining `str(exc)` leak in the backend.

### Fixed
- **Sync `package.json` version** (`frontend/package.json`) — Bumped `0.5.0` → `0.6.0` to match the `[0.6.0]` release tag.

---

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

### Backend (39 Python files)
```
backend/main.py
backend/config.py
backend/run_test_backend.py
backend/models/database.py
backend/models/project.py
backend/models/state.py
backend/models/characters.py
backend/models/segments.py
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
backend/services/prompts.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/test_projects.py
backend/tests/test_characters.py
backend/tests/test_character_timeline.py
backend/tests/test_segments.py
backend/tests/test_images.py
backend/tests/test_fireworks.py
backend/tests/test_video.py
backend/tests/test_prompts.py
backend/tests/test_schema_flatten.py
backend/tests/test_style_state.py
backend/tests/isolation_modules.py
backend/tests/test_isolation.py
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
| **v0.5.0** | 102 | 73 | 175 |
| **v0.6.0** | 114 | 73 | 187 |
| **v0.7.0** | 148 | 73* | 221 |
| **v0.7.1** | 149 | 73* | 222 |
| **v0.7.2** | 151 | 73* | 224 |
| **v0.7.3** | 154 | 73* | 227 |
| **v0.8.0** | 172 | 73* | 245 |
| **v0.8.1** | 181 | 73* | 254 |
| **v0.8.2** | 183 | 73* | 256 |
| **v0.8.3** | 196 | 73* | 269 |
| **v0.8.4** | 199 | 73* | 272 |
| **v0.8.9** | 221 | 73* | 294 |
| **v0.8.8** | 218 | 73* | 291 |
| **v0.8.7** | 215 | 73* | 288 |
| **v0.8.6** | 208 | 73* | 281 |
| **v0.8.5** | 207 | 73* | 280 |
| **v0.9.0** | 225 | 73* | 298 |

\* Frontend count last recorded at v0.6.0; v0.7.0 changed only TS types in `Step2Characters.tsx` (`tsc --noEmit` clean, no new specs added).

### Backend Test Breakdown (v0.9.0 — 225 tests)
- `test_fireworks.py` — 13 tests (client, base_url, retry logic, json_schema, error handling, invalid-JSON guard, model env override, timeout env override, timeout normalization)
- `test_characters.py` — 32 tests (extract, two-batch prompts, system/user split, invalid-enum 502, name-mismatch 502, missing script, prerequisite, failures, GET/PUT, two-version Call 2, anchor injection, missing-version 502, PUT invalidates downstream, pre-version schema loading, pre-version Call 2, extract/timeline/Call-2 max_tokens=16000, GET preserves prompt fields, GET legacy base_name backfill, 504 on timeout, name-drift resolved via normalized-name + positional fallback, extract invalidates downstream, timeline invalidates downstream, normalize-name conservative)
- `test_character_timeline.py` — 6 tests (happy path, 409 no-characters, duplicate name disambiguated, missing person backfilled, inconsistent anchor coalesced, single version default)
- `test_segments.py` — 46 tests (breakdown, prompts, split, merge, missing files, prerequisite, failures, always-batch primary path, style-anchor assertions, flashback non-monotonic, end-to-end override, Pass 2 versioned characters, single-segment regen, regen with character versions, regen bad index, breakdown max_tokens, invalid JSON 502, GET returns prompt fields, PUT persists prompt edits, PUT preserves omitted fields, pre-prompt safety, Pass 2 ValueError 502, regenerate ValueError 502, split preserves other segment fields, merge preserves other segment fields, segment_id lifecycle: breakdown/split/merge/update preserve or backfill UUIDs, Pass 2 max_tokens 16000, partial progress persisted on timeout, resume skips completed segments, small project single batch, idempotent when all complete, missing segment_index resilience)
- `test_images.py` — 18 tests (upload, non-PNG, wrong ratio, RGBA, low resolution, GET, not found, batch status, image-by-id resolution, lazy migration: stamps missing segment_ids and renames legacy `images/{index:04d}.png` files, migration idempotent)
- `test_projects.py` — 20 tests (CRUD, cascade, state machine, Whisper mock, not found, transcript, voiceover re-upload, invalidate_downstream, delete atomicity, chunked-transcription offsets, global 500 error shape, invalidate clears video state/output)
- `test_video.py` — 51 tests (generate, status, download, SRT, effects, ffmpeg mocks, zoompan filters, _write_progress timestamp, status .conduit segment count, FFMPEG_PATH env, .wav voiceover resolution)
- `test_prompts.py` — 34 tests (StyleProfile injection, 5 builders' anchors/rules, SHOT_TYPES, get_style fallback, Pass 2 no-placeholder assertion, prompt-contract JSON-key pinning: extraction/breakdown/front/turnaround/Pass-2, impostor/original appearance-inheritance guidance)
- `test_schema_flatten.py` — 2 tests (enum survives `_flatten_schema`, Pydantic rejects bad enum)
- `test_style_state.py` — 2 tests (style_id persisted on create, `get_style_id` default fallback)
- `test_isolation.py` — 1 test (meta-test: no unpatched PROJECTS_BASE_DIR modules)

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
- `POST /api/v1/projects/{uuid}/characters/timeline` — Generate character timeline versions
- `POST /api/v1/projects/{uuid}/characters/prompts` — Generate character prompts
- `GET /api/v1/projects/{uuid}/characters` — Get character list
- `PUT /api/v1/projects/{uuid}/characters` — Update characters

### Segments
- `POST /api/v1/projects/{uuid}/segments/breakdown` — Breakdown segments
- `POST /api/v1/projects/{uuid}/segments/prompts` — Generate segment prompts
- `GET /api/v1/projects/{uuid}/segments` — Get all segments
- `PUT /api/v1/projects/{uuid}/segments` — Update segments
- `PUT /api/v1/projects/{uuid}/segments/{segment_index}/effect` — Update segment effect
- `POST /api/v1/projects/{uuid}/segments/{segment_index}/split` — Split segment
- `POST /api/v1/projects/{uuid}/segments/{segment_index}/merge` — Merge segments
- `POST /api/v1/projects/{uuid}/segments/{segment_index}/prompt` — Regenerate single segment prompt

### Images
- `POST /api/v1/projects/{uuid}/images/{segment_index}` — Upload image
- `GET /api/v1/projects/{uuid}/images/{segment_index}` — Get image
- `GET /api/v1/projects/{uuid}/images/status` — Batch image-status map

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
- FastAPI 0.119.1
- Uvicorn 0.47.0
- Pydantic 2.13.4
- aiosqlite 0.21.0 (WAL mode)
- OpenAI SDK 2.38.0 (with `base_url` override for Fireworks)
- pydub 0.25.1
- srt 3.5.3
- pytest 9.0.3 + pytest-asyncio 1.3.0 + respx 0.23.1
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
- ffmpeg 8.1.1 (for video generation)
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
