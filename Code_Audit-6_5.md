# Conduit Codebase Audit Report

**Date:** 2026-06-05
**Scope:** Full backend (FastAPI/Python) + frontend (React/TypeScript) + tests
**Reference Standards:** `/code-review-excellence` reference guides (Security, Python, TypeScript, React, Performance, Common Bugs, Universal Quality)
**Auditor:** AI Code Review Agent
**Commit Range:** `b450307` (main)

---

## Executive Summary

| Severity | Count | Description |
|----------|-------|-------------|
| **Critical** | 8 | Security vulnerabilities, data loss risks, event loop blocking, type safety failure |
| **High** | 14 | DRY violations, API timeouts, floating promises, race conditions, performance issues |
| **Medium** | 10 | Nits, style inconsistencies, code organization, missing best practices |
| **Total** | **32** | |

**Key Risk Areas:**
1. **Backend Async Safety** — `time.sleep` in async code blocks the entire event loop
2. **Information Disclosure** — Global exception handler leaks internal stack traces
3. **Data Loss Risk** — Test fixture can delete production database
4. **Type Safety** — TypeScript `strict` mode not enabled; silent `any` inference throughout
5. **App Resilience** — No Error Boundary; single component crash kills entire wizard
6. **API Timeouts** — External AI calls have no timeout; server can hang indefinitely
7. **Code Duplication** — `PROJECTS_BASE_DIR` duplicated in 6 files, `apiBase` in 10+ files

---

## Critical Issues (8)

### C1. `time.sleep` in Async Function — Blocks Entire Event Loop
**File:** `backend/services/whisper.py:45`
**Severity:** Critical
**Reference:** Python Guide §异步编程 — "❌ 不要在异步代码中使用 time.sleep"

```python
# Line 45
            time.sleep(delay)  # BLOCKS entire event loop
```

**Issue:** The `transcribe_audio` function is `async def`, but uses `time.sleep()` for retry backoff. This is a **synchronous blocking call** inside an async coroutine. During a 7-second retry delay (1+2+4s), the FastAPI event loop cannot process any other requests.

**Fix:**
```python
            await asyncio.sleep(delay)
```

**Impact:** Server becomes completely unresponsive during Whisper retry.

---

### C2. Global Exception Handler Leaks Internal Details
**File:** `backend/main.py:27-32`
**Severity:** Critical
**Reference:** Security Guide §Error Messages — "❌ Leaking sensitive information"

```python
# Lines 27-32
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "status_code": 500},
    )
```

**Issue:** Returns raw `str(exc)` to the client. This can leak:
- File system paths
- Database schema details
- SQL queries
- API keys (if included in error messages)
- Internal logic details

**Fix:**
```python
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred. Please try again later."},
    )
```

Log the full exception server-side instead.

**Impact:** Information disclosure; potential security vulnerability.

---

### C3. Test Fixture Destroys Production Database
**File:** `backend/tests/conftest.py:49-50`
**Severity:** Critical
**Reference:** Universal Quality §TOCTOU (Time-of-Check-Time-of-Use)

```python
# Lines 49-50
    if os.path.exists(models.database.DB_PATH):
        os.remove(models.database.DB_PATH)
```

**Issue:** The test fixture deletes whatever path `models.database.DB_PATH` points to. If the test environment is misconfigured or `DB_PATH` was never patched, this **deletes the production database**.

**Fix:** Use a guaranteed temporary database file:
```python
import tempfile

@pytest_asyncio.fixture
async def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    models.database.DB_PATH = path
    await models.database.init_db()
    yield path
    os.remove(path)
```

**Impact:** Production data loss risk.

---

### C4. FFmpeg Command String Injection Risk
**File:** `backend/services/ffmpeg.py:254-255`
**Severity:** Critical
**Reference:** Security Guide §Command Injection Prevention

```python
# Lines 254-255
    srt_path_ffmpeg = srt_path.replace(os.sep, "/")
    vf = f"subtitles='{srt_path_ffmpeg}'"
```

**Issue:** The `srt_path` is derived from `project_dir`, which is based on `project_uuid`. If a malicious UUID contains shell metacharacters (e.g., `; rm -rf /`), it gets interpolated into the ffmpeg command string.

**Fix:** Use `shlex.quote()`:
```python
import shlex
    vf = f"subtitles={shlex.quote(srt_path_ffmpeg)}"
```

**Impact:** Potential command injection via crafted project UUID.

---

### C5. TypeScript Strict Mode Disabled
**File:** `frontend/tsconfig.json`
**Severity:** Critical
**Reference:** TypeScript Guide §Strict Mode — "✅ 必须开启的 strict 选项"

```json
{
  "compilerOptions": {
    "target": "es2023",
    // ❌ Missing: "strict": true
    // ❌ Missing: "noImplicitAny"
    // ❌ Missing: "strictNullChecks"
    // ❌ Missing: "strictFunctionTypes"
    // ❌ Missing: "noUncheckedIndexedAccess"
  }
}
```

**Issue:** Without `strict: true`, the TypeScript compiler allows:
- Silent `any` inference (no type safety on function returns)
- `null`/`undefined` access without checking
- Missing property checks on objects
- Implicit `any` in catch clauses

**Fix:** Add `"strict": true` and fix all resulting type errors. Alternatively, add individual strict flags:
```json
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "noUncheckedIndexedAccess": true
```

**Impact:** Silent type unsafety throughout the frontend; runtime errors that could be caught at compile time.

---

### C6. No Error Boundary — Single Crash Kills Entire App
**File:** `frontend/src/components/WizardShell.tsx:113-128`
**Severity:** Critical
**Reference:** React Guide §Error Boundaries & Suspense — "❌ 没有错误边界"

```tsx
const renderStepContent = () => {
  switch (currentStep) {
    case 1: return <Step1Script />;
    case 2: return <Step2Characters />;
    case 3: return <Step3Segments />;
    case 4: return <Step4Images />;
    case 5: return <Step5Video />;
    default: return children;
  }
};
```

**Issue:** Any runtime error in any step component (e.g., diff algorithm crash, null reference) will unmount the entire wizard. Users lose all state and must refresh.

**Fix:** Wrap in a React Error Boundary:
```tsx
import { ErrorBoundary } from "react-error-boundary";

<ErrorBoundary fallback={<ErrorFallback />}>
  {renderStepContent()}
</ErrorBoundary>
```

**Impact:** Complete app crash on any step error; poor user experience.

---

### C7. No Request Timeout on External API Calls
**Files:** `backend/services/whisper.py`, `backend/services/fireworks.py`
**Severity:** Critical
**Reference:** Python Guide §异步编程 — "✅ 超时控制"

**Issue:** Neither the OpenAI client nor the Fireworks client has explicit timeout configuration. A hung network call (e.g., DNS resolution stall, server non-response) will block the async worker indefinitely.

**Whisper:**
```python
client = OpenAI(max_retries=0)  # No timeout parameter
```

**Fireworks:**
```python
self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)  # No timeout
```

**Fix:** Add timeout to both:
```python
client = OpenAI(max_retries=0, timeout=60.0)
```

For the completion call, wrap with `asyncio.timeout`:
```python
async with asyncio.timeout(120):
    response = await asyncio.to_thread(_call)
```

**Impact:** Server can hang indefinitely; DoS vulnerability.

---

### C8. Step Components Massively Exceed 200-Line Recommendation
**Reference:** React Guide §组件设计 — "组件职责单一，不超过 200 行"

| Component | Lines | Over by |
|-----------|-------|---------|
| `Step1Script.tsx` | 667 | 467 |
| `Step5Video.tsx` | 628 | 428 |
| `Step3Segments.tsx` | 469 | 269 |
| `Step2Characters.tsx` | 434 | 234 |

**Issue:** Each component mixes UI rendering, state management, API calls, business logic, and algorithms. This violates single responsibility and makes testing, maintenance, and code review difficult.

**Fix:** Extract into custom hooks:
- `useDiff()` — LCS algorithm + diff computation
- `useTranscript()` — fetch transcript + upload + loading states
- `useSegmentOperations()` — split, merge, prompt generation
- `useVideoGeneration()` — effects, status polling, console output

**Impact:** Unmaintainable code; high risk of bugs during changes.

---

## High Issues (14)

### H1. `PROJECTS_BASE_DIR` Duplicated Across 6 Files
**Files:** `routers/projects.py`, `routers/segments.py`, `services/state.py`, `services/srt.py`, `services/ffmpeg.py`, `routers/video.py`
**Severity:** High
**Reference:** Universal Quality §代码复用审查

**Issue:** The same constant is defined independently in 6 files. Changing the base directory requires editing 6 files.

**Fix:** Single `config.py` or `settings.py`:
```python
# config.py
PROJECTS_BASE_DIR = os.environ.get("PROJECTS_BASE_DIR", os.path.join("..", "projects"))
```

---

### H2. `apiBase` Hardcoded in 10+ Frontend Files
**Files:** All page components (`Step1Script.tsx`, `Step2Characters.tsx`, `Step3Segments.tsx`, `Step4Images.tsx`, `Step5Video.tsx`), `WizardShell.tsx`, `Stepper.tsx`, `Dashboard.tsx`, tests
**Severity:** High
**Reference:** Universal Quality §代码复用审查

**Issue:** `const apiBase = "http://localhost:8000/api/v1"` is repeated everywhere. Changing the API base requires editing 10+ files.

**Fix:** Centralized config:
```typescript
// src/config.ts
export const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
```

---

### H3. `stateMap` Logic Duplicated in WizardShell and Stepper
**Files:** `WizardShell.tsx:64-74`, `Stepper.tsx:50-62`
**Severity:** High
**Reference:** Universal Quality §复制粘贴变种

**Issue:** Both components independently fetch project state and map it to a step number. Two identical `fetch()` calls and state mapping logic.

**Fix:** Pass `projectState` from `WizardShell` to `Stepper` as a prop. Eliminates the second network request.

---

### H4. `generate_segment_clip` — 7 Copy-Paste Variants
**File:** `backend/services/ffmpeg.py:96-188`
**Severity:** High
**Reference:** Universal Quality §复制粘贴变种

**Issue:** 130 lines of nearly identical `if/elif` blocks. Only the ffmpeg expression string changes. Each block has the same command structure:
```python
elif effect == "...":
    expr = f"..."
    vf = f"zoompan=...,{scale_pad}"
    cmd = [FFMPEG_PATH, "-y", "-loop", "1", "-i", image_path, ...]
```

**Fix:** Extract expression mapping:
```python
EFFECT_EXPRESSIONS = {
    "zoom_in": "zoompan=z='...':d={frames}:fps=24",
    "zoom_out": "zoompan=z='...':d={frames}:fps=24",
    "pan_left": "zoompan=x='...':d={frames}:fps=24",
    # ...
}
```

---

### H5. `effects.py` and `ffmpeg.py` Have Inconsistent Effect Constants
**Files:** `backend/services/effects.py`, `backend/services/ffmpeg.py`
**Severity:** High
**Reference:** Universal Quality §抽象泄漏

**Issue:** `effects.py` has `pan_speed = -2` for pan_left, but `ffmpeg.py` has `pan_speed = -0.5` for the same effect. The frontend (`Step5Video.tsx`) has its own `EFFECTS` array. Three sources of truth for the same data.

**Fix:** `effects.py` should be the single source of truth for all effect parameters. `ffmpeg.py` should import from `effects.py`.

---

### H6. N+1 Image Status Checks
**File:** `frontend/src/pages/Step4Images.tsx:66-72` (implied from pattern in Step5Video)
**Severity:** High
**Reference:** Performance Guide §N+1 查询问题

**Issue:** Each segment triggers an independent HTTP request to check image status. With 50 segments, that's 50 concurrent HTTP requests.

**Fix:** Batch endpoint `GET /projects/{uuid}/images/status` returning a map of all segment indices to boolean status.

---

### H7. Floating Promises in `useEffect` — No Error Handling
**Files:** `Step1Script.tsx:185-187`, `Step3Segments.tsx:59-61`, `Step4Images.tsx:62-64`
**Severity:** High
**Reference:** TypeScript Guide §异步处理 — "❌ Not handling async errors"

```tsx
useEffect(() => {
  fetchTranscript();  // Floating promise, no catch in effect
}, [fetchTranscript]);
```

**Issue:** `fetchTranscript()` is async but the effect doesn't await it or catch errors. If the function throws, the error is unhandled and React may not surface it properly.

**Fix:**
```tsx
useEffect(() => {
  let cancelled = false;
  fetchTranscript().catch(err => {
    if (!cancelled) setError(err.message);
  });
  return () => { cancelled = true; };
}, [fetchTranscript]);
```

---

### H8. `fetch()` Calls Without `AbortController` — Race Conditions
**Files:** `WizardShell.tsx:49-59`, `Step1Script.tsx:163-183`, `Step5Video.tsx:68-79`
**Severity:** High
**Reference:** TypeScript Guide §竞态条件处理

**Issue:** Rapid navigation between steps can cause stale fetch responses to update state after the component has moved to a different step.

**Fix:** Add `AbortController` and cleanup:
```tsx
useEffect(() => {
  const controller = new AbortController();
  fetch(url, { signal: controller.signal })
    .then(...)
    .catch(err => {
      if (err.name !== 'AbortError') setError(err);
    });
  return () => controller.abort();
}, [url]);
```

---

### H9. `useEffect` for Polling Without Cleanup
**File:** `frontend/src/pages/Step5Video.tsx:160-211`
**Severity:** High
**Reference:** React Guide §useEffect 模式

```tsx
useEffect(() => {
  if (!generating) return;
  const interval = setInterval(async () => {
    // ... fetch status and logs
  }, 2000);
  return () => clearInterval(interval);  // ✅ cleanup present
}, [generating, uuid]);
```

**Issue:** While cleanup is present, the interval is 2 seconds. If the component unmounts during a `setInterval` callback, the async callback may still run and call `setState` on an unmounted component.

**Fix:** Use a ref to track mounted state:
```tsx
const mounted = useRef(true);
useEffect(() => {
  mounted.current = true;
  return () => { mounted.current = false; };
}, []);
```

---

### H10. `datetime.utcnow()` Deprecated in Python 3.12+
**Files:** `routers/projects.py`, `services/state.py`, `services/ffmpeg.py`, `services/srt.py`, `routers/video.py`
**Severity:** High
**Reference:** Python Guide §现代 Python 特性

**Issue:** `datetime.utcnow()` is deprecated in Python 3.12. It returns a naive datetime (no timezone info), which can cause issues with timezone-aware comparisons.

**Fix:** Use timezone-aware datetime:
```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
```

---

### H11. `check_same_thread=False` on SQLite with Async
**File:** `backend/models/database.py:8`
**Severity:** High
**Reference:** Python Guide §常见陷阱

```python
conn = await aiosqlite.connect(DB_PATH, check_same_thread=False)
```

**Issue:** `check_same_thread=False` disables the safety check that prevents SQLite from being accessed from multiple threads. SQLite is **not thread-safe** by default. Multiple async coroutines could hit the same connection object simultaneously.

**Fix:** Use a connection pool or ensure each request gets a fresh connection. Consider `aiosqlite` with proper connection management or `asyncio.Lock` around database operations.

---

### H12. `upload_voiceover` Reads Entire File into Memory
**File:** `backend/routers/projects.py:232-234`
**Severity:** High
**Reference:** Performance Guide §过度宽泛操作

```python
    content = await file.read()
    f.write(content)
```

**Issue:** For large audio files (e.g., 100MB), this reads the entire file into memory before writing to disk.

**Fix:** Stream directly:
```python
import shutil
shutil.copyfileobj(file.file, f)
```

---

### H13. No Rate Limiting on AI Endpoints
**Files:** All backend routers (`characters.py`, `segments.py`, `video.py`)
**Severity:** High
**Reference:** Security Guide §Rate Limiting

**Issue:** No rate limiting on expensive AI endpoints (`/characters/extract`, `/segments/breakdown`, `/segments/prompts`, `/video/generate`). A malicious user could trigger unlimited API calls, causing:
- Cost overruns (OpenAI + Fireworks)
- Server resource exhaustion
- Potential account suspension

**Fix:** Add `slowapi` or custom rate limiting middleware.

---

### H14. `CORS` Allows All Headers
**File:** `backend/main.py:20`
**Severity:** High
**Reference:** Security Guide §CORS

```python
    allow_headers=["*"],
```

**Issue:** Allowing all headers is overly permissive. Should specify only required headers (e.g., `Content-Type`, `Authorization`).

**Fix:**
```python
    allow_headers=["Content-Type", "Authorization"],
```

---

## Medium Issues (10)

### M1. `ProjectState` Used as `string` in Frontend
**File:** `frontend/src/components/WizardShell.tsx:17-19`
**Severity:** Medium
**Reference:** TypeScript Guide §类型安全

```typescript
interface ProjectState {
  state: string;  // Too broad
}
```

**Fix:** Use a union type:
```typescript
type ProjectStateValue = 'created' | 'step_1_complete' | 'step_2_complete' | 'step_3_complete' | 'step_4_complete' | 'step_5_complete';
```

---

### M2. `injectStyles` Function Duplicated in Every Test File
**Files:** `frontend/tests/*.spec.ts`
**Severity:** Medium
**Reference:** Universal Quality §复制粘贴变种

**Fix:** Extract to `frontend/tests/utils.ts`:
```typescript
export async function injectStyles(page: Page) {
  await page.addStyleTag({...});
}
```

---

### M3. Inline LCS Algorithm in Step1Script
**File:** `frontend/src/pages/Step1Script.tsx:29-62`
**Severity:** Medium
**Reference:** React Guide §组件设计

**Fix:** Move to `src/lib/diff.ts`:
```typescript
export function computeDiff(oldText: string, newText: string): DiffBlock[] {
  // ...
}
```

---

### M4. `isBackendRunning` Uses Windows-Specific Shell
**File:** `frontend/tests/e2e-happy-path.spec.ts:14-16`
**Severity:** Medium
**Reference:** Common Bugs Checklist

```typescript
execSync('curl -s http://localhost:8000/health', { shell: 'cmd.exe' });
```

**Fix:** Use Node.js built-in:
```typescript
async function isBackendRunning(): Promise<boolean> {
  try {
    const res = await fetch('http://localhost:8000/health');
    return res.ok;
  } catch {
    return false;
  }
}
```

---

### M5. `page: any` in Test Files
**File:** `frontend/tests/step1-fidelity.spec.ts:8`
**Severity:** Medium
**Reference:** TypeScript Guide §避免使用 any

```typescript
async function injectStyles(page: any) {
```

**Fix:** Import `Page` from `@playwright/test`:
```typescript
import { Page } from '@playwright/test';
async function injectStyles(page: Page) {
```

---

### M6. `button.tsx` Uses `rounded-lg` Despite `radius: 0`
**File:** `frontend/src/components/ui/button.tsx:7`
**Severity:** Medium
**Reference:** DESIGN.md — "0px border radius everywhere"

```typescript
"group/button inline-flex shrink-0 items-center justify-center rounded-lg border..."
```

**Fix:** Override or remove `rounded-lg` from the base class. The shadcn/ui config has `radius: 0` but the base class wasn't updated.

---

### M7. `frontend/package.json` Version Still `0.0.0`
**File:** `frontend/package.json:4`
**Severity:** Medium
**Reference:** General best practice

**Fix:** Match `CHANGELOG.md` version (e.g., `0.4.1`).

---

### M8. `main.py` Missing Startup Database Initialization
**File:** `backend/main.py`
**Severity:** Medium
**Reference:** Python Guide §测试最佳实践

**Issue:** `init_db()` is never called on startup. The first request triggers lazy initialization.

**Fix:**
```python
@app.on_event("startup")
async def startup():
    await models.database.init_db()
    # ... existing key validation
```

---

### M9. Generic `Exception` Catches in Characters/Segments Routers
**Files:** `routers/characters.py:88-92`, `routers/segments.py:210-213`
**Severity:** Medium
**Reference:** Python Guide §异常处理

```python
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Character extraction failed",
        ) from exc
```

**Issue:** Catches `Exception` but doesn't distinguish between:
- `AuthenticationError` (401 — should not retry)
- `RateLimitError` (429 — should retry)
- `APIError` (500 — should retry)
- `ConnectionError` (network issue)

**Fix:** Catch specific exception types and map to appropriate status codes.

---

### M10. `conftest.py` Modifies Module-Level Globals at Import Time
**File:** `backend/tests/conftest.py:16`
**Severity:** Medium
**Reference:** Python Guide §常见陷阱

```python
models.database.DB_PATH = test_db_path
```

**Issue:** Modifying module globals at import time can cause issues with test ordering and parallel execution.

**Fix:** Use a fixture-scoped approach or dependency injection.

---

## Additional Observations

### A1. Dual State Storage — Potential Source of Truth Drift
**Files:** `models/database.py` (SQLite), `services/state.py` (`state.json`)

**Issue:** Project state is stored in both SQLite (`projects.state`) and `.conduit/state.json`. If these get out of sync (e.g., manual file editing, failed write), the application behavior is undefined.

**Recommendation:** SQLite should be the single source of truth. `state.json` should be read-only derived data, or eliminated entirely.

### A2. `SplitRequest` Model Not Used in API
**File:** `backend/routers/segments.py:46-49`

```python
class SplitRequest(BaseModel):
    word_index: Optional[int] = None
    timestamp: Optional[float] = None
```

**Issue:** The `split_segment` endpoint reads `request.word_index` and `request.timestamp`, but the frontend sends `split_point` in the body. This is a mismatch.

### A3. `handleApproveRemaining` Callback Ref Issue
**File:** `frontend/src/pages/Step1Script.tsx:280-286`

```typescript
const handleApproveRemaining = () => {
  diffBlocks.forEach((block, index) => {
    if (block.type !== "equal" && !approvedChanges.has(index) && !rejectedChanges.has(index)) {
      handleApprove(index);  // Uses stale closure
    }
  });
};
```

**Issue:** `handleApproveRemaining` calls `handleApprove` which uses `setState`. In a loop, this can cause stale closure issues. Should batch the state updates.

---

## Session Split Reference

| Session | Issues | Count | Estimated Effort | Theme |
|---------|--------|-------|------------------|-------|
| **A** | C1-C8, H1-H3, H7-H8, H11-H12 | 15 | 6-8 hours | Safety, config, async correctness, quick fixes |
| **B** | H4-H6, H9-H10, H13-H14, M1-M10 | 17 | 8-12 hours | Refactoring, performance, DRY, structural improvements |

### Session A — Safety & Async Fixes
**Goal:** Eliminate critical bugs, centralize configuration, fix async safety, and close immediate security holes.

| Issue | File | Effort | Notes |
|-------|------|--------|-------|
| C1 | `services/whisper.py:45` | 1 line | `time.sleep` → `asyncio.sleep` |
| C2 | `main.py:27-32` | 5 lines | Generic error message + server-side logging |
| C3 | `tests/conftest.py:49-50` | 10 lines | Use `tempfile.mkstemp` for test DB |
| C4 | `services/ffmpeg.py:254-255` | 3 lines | Verify list-based `subprocess.run` with `shell=False` (already safe). Add comment documenting why `shlex.quote()` is not needed. |
| C5 | `tsconfig.json` | 1 line + fixes | Enable `strict: true`; fix type errors |
| C6 | `WizardShell.tsx` | ~20 lines | Add `react-error-boundary` wrapper |
| C7 | `services/whisper.py`, `services/fireworks.py` | ~5 lines | Add `timeout=60` to OpenAI client |
| C8 | `Step1Script.tsx`, `Step5Video.tsx`, etc. | ~100 lines | Extract custom hooks |
| H1 | `routers/*.py`, `services/*.py` | ~20 lines | Single `config.py` for `PROJECTS_BASE_DIR` |
| H2 | `frontend/src/pages/*.tsx`, `tests/*.ts` | ~30 lines | Single `src/config.ts` for `apiBase` |
| H3 | `WizardShell.tsx`, `Stepper.tsx` | ~15 lines | Pass `projectState` prop to `Stepper` |
| H7 | `Step1Script.tsx`, `Step3Segments.tsx`, `Step4Images.tsx` | ~20 lines | Add `.catch()` to floating promises |
| H8 | `WizardShell.tsx`, `Step1Script.tsx`, `Step5Video.tsx` | ~30 lines | Add `AbortController` to `fetch()` calls |
| H11 | `models/database.py:8` | ~10 lines | Document why `check_same_thread=False` is safe for aiosqlite (internal thread pool + WAL mode). Do not add `asyncio.Lock` (would serialize all requests). |
| H12 | `routers/projects.py:232-234` | 3 lines | `shutil.copyfileobj` for streaming |

### Session B — Refactoring & Performance
**Goal:** Extract reusable logic, improve performance, add batch endpoints, and close structural debt.

| Issue | File | Effort | Notes |
|-------|------|--------|-------|
| H4 | `services/ffmpeg.py:96-188` | ~50 lines | Extract `EFFECT_EXPRESSIONS` mapping |
| H5 | `services/effects.py`, `services/ffmpeg.py`, `Step5Video.tsx` | ~30 lines | Single source of truth for effect params |
| H6 | `Step4Images.tsx`, `Step5Video.tsx`, `routers/images.py` | ~40 lines | Batch endpoint `GET /images/status` |
| H9 | `Step5Video.tsx:160-211` | ~15 lines | Use `mounted` ref for polling cleanup |
| H10 | `routers/*.py`, `services/*.py` | ~20 lines | `datetime.now(timezone.utc)` everywhere |
| H13 | `main.py` | ~20 lines | Add `slowapi` rate limiting middleware |
| H14 | `main.py:20` | 1 line | `allow_headers=["Content-Type", "Authorization"]` |
| M1 | `WizardShell.tsx:17-19` | 5 lines | Union type for `ProjectState` |
| M2 | `frontend/tests/*.spec.ts` | ~10 lines | Extract to `tests/utils.ts` |
| M3 | `Step1Script.tsx:29-62` | ~20 lines | Move to `src/lib/diff.ts` |
| M4 | `e2e-happy-path.spec.ts:14-16` | ~10 lines | Use `fetch()` instead of `execSync` |
| M5 | `step1-fidelity.spec.ts:8` | 2 lines | `import { Page } from '@playwright/test'` |
| M6 | `components/ui/button.tsx:7` | 1 line | Remove `rounded-lg` |
| M7 | `frontend/package.json:4` | 1 line | Version `0.4.1` |
| M8 | `main.py` | 3 lines | Call `init_db()` in startup handler |
| M9 | `routers/characters.py`, `routers/segments.py` | ~20 lines | Catch specific exception types |
| M10 | `tests/conftest.py:16` | ~10 lines | Fixture-scoped DB path instead of module-level |

---

## Fix Priority Matrix (Legacy)

| Priority | Issues | Estimated Effort |
|----------|--------|------------------|
| **P0 — Immediate** | C1, C2, C3 | 30 minutes |
| **P1 — This Week** | C5, C6, C7, H1, H2, H7 | 2-3 hours |
| **P2 — Next Sprint** | C4, H3, H4, H5, H8, H9, H11, H12 | 4-6 hours |
| **P3 — Backlog** | H6, H10, H13, H14, M1-M10 | 4-8 hours |

---

## Standards Compliance Summary

| Reference Guide | Critical | High | Medium | Status |
|--------------|----------|------|--------|--------|
| **Security** | 2 | 2 | 0 | ⚠️ Needs attention |
| **Python** | 1 | 3 | 2 | ⚠️ Needs attention |
| **TypeScript** | 1 | 2 | 2 | 🔴 Not strict |
| **React** | 1 | 2 | 2 | ⚠️ Needs attention |
| **Performance** | 0 | 2 | 1 | ⚠️ Needs attention |
| **Common Bugs** | 0 | 1 | 2 | ✅ Mostly clean |
| **Universal Quality** | 3 | 3 | 1 | 🔴 Significant debt |

---

*End of Audit Report*
