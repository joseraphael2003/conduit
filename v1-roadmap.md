# Conduit — v1 Roadmap

**Purpose:** This document is the strategic anchor for the project. It captures the high-level session plan, critical dependencies, and risk decisions. It is **not** an implementation plan — that is written per-session using the `prometheus` skill.

**Status:** Ready to scaffold
**Target:** 4 sessions, backend-first, wizard workflow

---

## Session 1: Foundation (Phases 0–3)

**Goal:** The backend API exists, the frontend shell renders, and Step 1 (Script) is fully functional.

**Phases:**
1. **Phase 0: Project Scaffolding** — FastAPI backend + React/Vite frontend + Tailwind v4 + shadcn/ui configured
2. **Phase 1: Backend Core** — SQLite schema, project CRUD, file storage, cascade state machine
3. **Phase 2: Frontend Shell** — Wizard layout (Title Bar + Stepper + Content + Action Bar), dashboard, theme applied
4. **Phase 3: Step 1 — Script Backend** — Whisper API integration, chunking, SRT generation, word-level JSON

**Checkpoint Rule:**
- **Hard commitment:** Phases 0–3 (backend APIs for Step 1)
- **Stretch goals:** Phase 4 (Step 1 Frontend) and Phase 5 (Step 2 Backend)
- **Fallback:** If Session 1 ends before Phase 5 is done, Phase 4 moves to Session 2. The backend is the priority.

**Critical dependencies locked in this session:**
- Monorepo structure (`backend/`, `frontend/`)
- API base URL: `http://localhost:8000/api/v1`
- Project storage: `./projects/{uuid}/`
- State machine: `created` → `step_1_complete` → `step_2_complete` ...
- Cascade rule: editing Step N invalidates Steps N+1–5
- shadcn/ui override: `radius: 0`, no shadows, `@phosphor-icons/react`

---

## Session 2: Wizard Body (Phases 4–10)

**Goal:** Steps 1–4 are complete (both backend and frontend). The user can upload a voiceover, extract characters, generate segments, and upload images.

**Phases:**
5. **Phase 4: Step 1 — Script Frontend** — Voiceover dropzone, transcript display, progress, Next button
6. **Phase 5: Step 2 — Characters Backend** — Fireworks AI character extraction (Call 1) + prompt generation (Call 2)
7. **Phase 6: Step 2 — Characters Frontend** — Character table, edit descriptions, prompt cards, copy button
8. **Phase 7: Step 3 — Segments Backend** — Segment breakdown + prompt generation (single call + batch fallback)
9. **Phase 8: Step 3 — Segments Frontend** — Segment table, edit prompts, split/merge
10. **Phase 9: Step 4 — Images Backend** — Per-segment PNG upload, 16:9 validation, RGBA→RGB conversion
11. **Phase 10: Step 4 — Images Frontend** — Grid upload, thumbnails, placeholders, upload modal

**Session 2 risk:** If Session 1 didn't finish Phase 5 (Step 2 Backend), Session 2 must start there. This is the only carry-over risk.

---

## Session 3: Video Generation (Phases 11–12)

**Goal:** Step 5 is complete. The user can generate a 1080p24 MP4 with motion effects, optional caption burn, and download.

**Phases:**
12. **Phase 11: Step 5 — Video Backend** — ffmpeg per-segment clip generation, concat, audio mix, optional caption burn
13. **Phase 12: Step 5 — Video Frontend** — Effect selection, auto-assign, randomize, progress bar, console output, download

**Why isolated in its own session:**
- ffmpeg is the highest-risk technical surface. Filter graph syntax, codec compatibility, and progress streaming are unpredictable.
- This session may need 2–3 iterations of ffmpeg debugging. Isolating it prevents it from blowing up the Session 2 schedule.

---

## Session 4: Polish & Integration (Phase 13)

**Goal:** Cascade rules are bulletproof, error handling covers all 9 scenarios, accessibility is complete, and the full workflow is validated end-to-end.

**Phase:**
14. **Phase 13: Cascade Rules + Polish** — Integration testing, edge cases, error handling, accessibility, loading states, validation

**End-to-end test path:**
1. Create project → Upload voiceover → Transcription → Next
2. Extract characters → Edit → Generate prompts → Next
3. Generate segments → Review → Next
4. Upload images (all segments) → Next
5. Auto-assign effects → Generate video → Download MP4 + SRT

**Edge cases to validate:**
- 60-minute voiceover (chunking)
- No original script provided
- Editing Step 2 after Step 4 is complete (cascade)
- Missing images (Step 5 blocked)
- ffmpeg failure mid-generation (retry from segment N)

---

## Session Split Logic

| Session | Phases | Focus | Est. Hours | Cumulative |
|---------|--------|-------|------------|------------|
| **1** | 0–3 | Backend foundation + Step 1 | 8–13 | 13 |
| **2** | 4–10 | Frontend wiring + Steps 2–4 | 7–12 | 25 |
| **3** | 11–12 | ffmpeg + Step 5 | 4–6 | 31 |
| **4** | 13 | Cascade + Polish + Testing | 2–3 | 34 |
| **A** | Audit fixes | Safety, async, config, type safety | 6–8 | 40–42 |
| **B** | (planned) | Refactoring, performance, DRY | 8–12 | 48–54 |

**Reality estimate:** 35–40 hours total (Sessions 1–4). Session A + B add ~14–20 hours for audit remediation.

---

## Risk Register

| Risk | Mitigation | Owner |
|------|-----------|-------|
| ffmpeg filter graph fails | Build minimal prototype in Session 1 (standalone script) | Session 3 |
| Whisper API rate limit / 25MB chunking | Exponential backoff, parallel chunk upload | Session 1 |
| Fireworks AI `json_schema` limitations | Flat schemas, no `oneOf`, no `pattern` | Session 2 |
| Session 1 runs long (Phases 4–5 not done) | Phase 4 moves to Session 2; backend is priority | Session 1 |
| shadcn/ui defaults conflict with DESIGN.md | `radius: 0`, no shadows, Phosphor icons override | Session 1 |
| Design token export issues | Manual handling of `border`, `transform`, `max-width` | Session 1 |

---

## Design Anchors

- **DESIGN.md** — Theme system, tokens, colors, typography, components
- **DESIGN_SPEC.md** — Technical specification, API prompts, data models, error handling

These two files are the single source of truth for all visual and technical decisions. Any deviation during implementation must be documented in the session plan.

---

## Next Action

**Session B begins.** Fix remaining 17 audit issues (H4–H6, H9–H10, H13–H14, M1–M10).
