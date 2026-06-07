# AGENTS.md — Conduit

Conduit is a local web app that turns a voiceover audio file + optional script into a 1080p 24fps YouTube video with AI-generated scene images, motion effects, and burned captions. It runs on `http://localhost:8000` — single user, no auth, no cloud deployment.

---

## Repository Layout

```
Media Pipeline/
├── backend/               # FastAPI app (Python 3.12+)
│   ├── main.py            # App entry point, router registration
│   ├── config.py          # Settings / env var loading
│   ├── models/            # Pydantic models + SQLite schema (database.py, project.py, state.py, characters.py, segments.py)
│   ├── routers/           # One file per step: projects, characters, segments, images, video
│   ├── services/          # Business logic: whisper, fireworks, ffmpeg, srt, state, chunking, effects, prompts
│   └── tests/             # pytest tests (conftest.py + per-router test files)
├── frontend/              # React + Vite app (TypeScript strict)
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── config.ts      # API base URL
│       ├── pages/         # Step1Script, Step2Characters, Step3Segments, Step4Images, Step5Video, Dashboard
│       ├── components/    # WizardShell, Stepper, AmberBar, SkeletonTable, ui/button
│       ├── hooks/         # useDiff, useTranscript, useFocusTrap
│       └── styles/        # theme.css (CSS vars from DESIGN.md), index.css
├── DESIGN_SPEC.md         # Full product spec — the source of truth for behavior
├── DESIGN.md              # Design system — colors, typography, components, do's/don'ts
└── Research/              # Background research (read-only, do not modify)
```

---

## Commands

### Backend

```bash
# From repo root
cd backend

# Install dependencies
pip install -r requirements.txt

# Run dev server (with auto-reload)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Run all tests
pytest

# Run a specific test file
pytest tests/test_characters.py -v

# Run tests without hitting real APIs (mark-based)
pytest -m "not integration"
```

**Environment:** Requires a `.env` file at `backend/.env`. See `backend/.env.example` for required keys:
- `OPENAI_API_KEY` — Whisper transcription
- `FIREWORKS_API_KEY` — LLM calls (character extraction, segment prompts, cross-reference)

### Frontend

```bash
# From repo root
cd frontend

# Install dependencies
npm install

# Dev server (http://localhost:5173 by default, proxies API to :8000)
npm run dev

# Type check (zero errors required)
npx tsc --noEmit

# Build
npm run build
```

---

## Architecture Rules

### Backend

- **No shell=True.** All `subprocess.run` calls for ffmpeg must use a list of arguments, never a shell string. No `shlex.quote()` needed when using list form.
- **Never return `str(exc)` to the client.** Log full exceptions server-side; return a generic message to the frontend.
- **Async throughout.** All route handlers are `async def`. Use `asyncio.timeout(120)` for Fireworks calls, `timeout=60.0` on the OpenAI client.
- **Pydantic v2.** Use `model_validate`, `model_dump`, and `BaseModel` from `pydantic`. Do not use v1-style `.dict()` or `.parse_obj()`.
- **State lives in SQLite.** Project state is persisted in the SQLite DB (`models/database.py`). No in-memory state that would be lost on server restart.
- **Project isolation.** Each project gets a UUID subfolder under `./projects/{uuid}/`. Never construct file paths with string concatenation — always use `pathlib.Path` joins.
- **Retry logic.** Whisper and Fireworks calls retry 3× with exponential backoff (1s, 2s, 4s) before surfacing an error.

### Frontend

- **TypeScript strict mode.** Zero type errors. No `any` unless absolutely unavoidable with a comment explaining why.
- **No client-side state management library.** State is server-side (SQLite). Use `useState` and `useEffect` with fetch calls. No Redux, Zustand, etc.
- **Design system is law.** All UI must follow `DESIGN.md`. Key rules:
  - 0px border-radius everywhere — no rounded corners
  - No box shadows — elevation via surface brightness
  - No gradients — solid colors only
  - Dark mode only — no light theme, no light panels
  - Amber (`#F0A040`) for primary actions only — not decorative
  - Icons: `@phosphor-icons/react` (priority) or `@tabler/icons-react` (fallback). Never `lucide-react`
  - Fonts: Playfair Display (headlines), Source Sans 3 (body), JetBrains Mono (technical data)
- **No mobile breakpoints.** Desktop-only, minimum 1280px viewport.
- **No browser default file inputs.** Always use the custom dropzone component.

---

## Step Behavior (Critical)

Read `DESIGN_SPEC.md` for full detail. Key rules agents must not break:

1. **Cascade Rule:** Editing any step invalidates all downstream steps. Step 2 edits → Steps 3–5 reset. Always enforce this in both the UI and the backend state model.
2. **Step 1 Next button:** Enabled when transcript is present. If original script is present and fidelity < 95%, show a non-blocking warning modal (not a hard block).
3. **Step 2 is mandatory.** No skip option. Two distinct LLM calls: Call 1 = character extraction, Call 2 = prompt generation. Call 2 is only enabled after Call 1 completes and user has reviewed.
4. **Step 3 segments:** Two-pass AI approach — Pass 1 breaks the script into segments with timestamps, Pass 2 generates image prompts. Single API call preferred; overlapping-batch fallback if token limit hit.
5. **Step 4 images:** One upload per segment, no bulk upload. Validate 16:9 aspect ratio and minimum 1920×1080. Auto-convert RGBA → RGB. Warn (don't block) on sub-minimum resolution.
6. **Step 5 video:** Each segment gets a randomly auto-assigned motion effect (pan left/right/up/down, zoom in/out). User can override individual segments. Hard cuts only — no crossfade.

---

## AI Providers

| Provider | SDK | Used For |
|----------|-----|----------|
| OpenAI | `openai` Python SDK | Whisper transcription (`whisper-1`, `verbose_json` format, word-level timestamps) |
| Fireworks AI | `openai` SDK (OpenAI-compatible) | All LLM calls — base URL `https://api.fireworks.ai/inference/v1`, model `accounts/fireworks/routers/kimi-k2p6-turbo` |

All LLM calls use **structured outputs** (`json_schema` / Pydantic response models). Never ask the model to return free-form text for machine-consumed data.

---

## Data Files (Per Project)

```
projects/{uuid}/
├── voiceover.mp3
├── original_script.md       # Optional
├── words.json               # Whisper word-level timestamps
├── transcript_raw.txt
├── source_of_truth_script.txt
├── characters.json
├── segments.json
├── captions.srt
├── captions.ass             # Optional, generated if captions burned
├── images/
│   ├── 0001.png
│   └── ...
└── output/
    └── output.mp4
```

---

## What Not to Touch

- `Research/` — background research docs, read-only
- `backend/.env` — never commit or log API keys
- `DESIGN.md` / `DESIGN_SPEC.md` — do not modify unless explicitly asked; these are the source of truth
- `backend/tests/fixtures/` — test fixtures, do not modify without updating the tests that use them

---

## Off-Limits Actions

- Do not run `ffmpeg` with `shell=True`
- Do not return exception details to the HTTP client
- Do not add rounded corners, box shadows, or gradients to frontend components
- Do not use `lucide-react`
- Do not add mobile/responsive CSS breakpoints
- Do not use `git commit --no-verify`
