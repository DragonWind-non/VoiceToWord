# Code Cleanup and Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean internal module logic, streamline memory usage, resolve Win32 64-bit API handle truncations, and decouple Windows low-level keyboard hook threads from blocking audio/injection operations.

**Architecture:** Refactor `AudioRecorder` to calculate RMS efficiently on native integer buffers and treat non-fatal PortAudio flags gracefully. Refine `Transcriber` to access segment data safely and disambiguate CLI prefixes from common English speech. Update `TextInjector` ctypes allocation to direct indexed population. Ensure `OverlayIndicator` uses 64-bit Win32 types, race-free error timer versioning, and complete type annotations. Refactor `VoiceToWordApp` in `main.py` so the `WH_KEYBOARD_LL` hook callback returns immediately while background workers handle audio shutdown, silence checking, and text injection.

**Tech Stack:** Python 3.12, ctypes (Win32 API), sounddevice/numpy, Groq API (whisper-large-v3-turbo), pynput, tkinter.

**Spec:** Review findings and design agreements from session 2026-10-25 (resolving 10 code-review items).

## Global Constraints

- OS: Windows 11 64-bit.
- Type hints: 100% type annotations on all methods and functions per project `CLAUDE.md`.
- Concurrency: Never execute blocking I/O, audio buffer conversions, or synchronous IPC (`SendMessageTimeoutW`) inside the `WH_KEYBOARD_LL` hook thread callback.
- Formatting: Clean, minimal diffs following Ponytail full mode.

## Review Focus

1. PortAudio callback warning flags (`input_underflow`) must not abort recording or drop captured speech.
2. Whisper segment parsing with null or missing `"text"` must not raise `KeyError` or fail transcription.
3. Natural English sentences starting with words like "Go", "Code", or "Cat" must preserve trailing punctuation while technical CLI commands strip trailing periods.
4. Overlay indicator window styles on 64-bit Windows must use pointer-sized types (`LONG_PTR`, `HWND`) to prevent handle truncation and focus-stealing.
5. Error notification dismiss timers in `OverlayIndicator` must not dismiss newer error messages prematurely when multiple errors are emitted concurrently.

---

### Task 1: Clean and Optimize `AudioRecorder` (`src/audio_recorder.py`)

**Files:**
- Modify: `src/audio_recorder.py`
- Test: `tests/test_audio_recorder.py`, `tests/test_stability.py`

**Interfaces:**
- Consumes: `sounddevice.InputStream`, `numpy`
- Produces:
  - `AudioRecorder.is_silent(threshold_dbfs: float = -60.0, data: Optional[np.ndarray] = None) -> bool`
  - `AudioRecorder.stop() -> Tuple[io.BytesIO, float]`

- [ ] **Step 1: Write tests for non-fatal status flags and optimized silence check**

Add unit tests in `tests/test_audio_recorder.py`:
- `test_non_fatal_status_flags_do_not_abort_recording`: call `_audio_callback` with `status.input_underflow = True`, verify `_audio_error` is not set and `stop()` succeeds.
- `test_is_silent_accepts_preconcatenated_data`: call `is_silent` passing pre-concatenated numpy array, verifying identical silence detection without allocating duplicate arrays.

- [ ] **Step 2: Run tests to verify they fail or need implementation**

Run: `python -m pytest tests/test_audio_recorder.py -v`

- [ ] **Step 3: Implement changes in `src/audio_recorder.py`**

- In `_audio_callback`: Only set `self._audio_error = "Audio input overflow"` when `status.input_overflow` is true. For other flags (like underflow), log a warning or ignore without raising `RuntimeError`.
- In `is_silent`: Accept an optional `audio_data: Optional[np.ndarray] = None`. If provided, use it directly; otherwise concatenate `self.frames`. Compute DC-centered RMS using `int32` intermediate array (`frame.astype(np.int32)`) to avoid heavy `float64` allocations while preventing overflow.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_audio_recorder.py tests/test_stability.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/audio_recorder.py tests/test_audio_recorder.py
git commit -m "fix(audio): handle non-fatal status flags and optimize silence analysis"
```

---

### Task 2: Robust Segment Parsing and CLI Prefix Disambiguation in `Transcriber` (`src/transcriber.py`)

**Files:**
- Modify: `src/transcriber.py`
- Test: `tests/test_transcriber.py`

**Interfaces:**
- Consumes: Groq Whisper API `verbose_json` response, `clean_transcription(text: str) -> str`
- Produces: Safe `transcribe(audio_buffer: io.BytesIO) -> str`

- [ ] **Step 1: Write tests for segment safety and common English sentences**

In `tests/test_transcriber.py`:
- `test_transcribe_handles_segments_with_missing_text`: mock Groq segment with `{"no_speech_prob": 0.01}` (missing `"text"` key) or `{"text": None}`, verify transcription completes without `KeyError` or crash.
- Add sentences to `test_clean_transcription_regular_sentences`:
  - `"Go to the store."` -> `"Go to the store."`
  - `"Code of conduct."` -> `"Code of conduct."`
  - `"Cat is sleeping."` -> `"Cat is sleeping."`
- Add CLI tests to `test_clean_transcription_cli_commands`:
  - `"go run main.go."` -> `"go run main.go"`
  - `"code ."` -> `"code ."`
  - `"cat file.txt."` -> `"cat file.txt"`

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_transcriber.py -v`
Expected: FAIL on `"Go to the store."` stripping period.

- [ ] **Step 3: Implement changes in `src/transcriber.py`**

- In `clean_transcription`:
  - Split CLI prefixes into:
    - Pure technical CLI tools (always strip trailing period if followed by space or alone): `git`, `docker`, `npm`, `pnpm`, `yarn`, `pip`, `python`, `python3`, `curl`, `kubectl`, `ssh`, `node`, `deno`, `bun`, `cargo`, `rustc`, `pytest`.
    - Contextual CLI tools (`go`, `code`, `cat`): only strip period if accompanied by typical CLI patterns (e.g. `go run`, `go build`, `go test`, `go get`, `code .`, `code -`, flags `-*`, `--*`).
- In `Transcriber.transcribe`:
  - Safely extract segment text: `part = segment.get("text") or ""` before calling `part.strip()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_transcriber.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/transcriber.py tests/test_transcriber.py
git commit -m "fix(transcriber): safe segment access and disambiguate CLI punctuation heuristics"
```

---

### Task 3: Simplify and Direct-Index `INPUT` Array in `TextInjector` (`src/injector.py`)

**Files:**
- Modify: `src/injector.py`
- Modify: `tests/test_injector.py` (add defensive skip for broken host Tkinter)

**Interfaces:**
- Consumes: `ctypes.wintypes`, `KEYBDINPUT`, `INPUT`
- Produces: `TextInjector.paste_text(text: str) -> bool`

- [ ] **Step 1: Write test for indexed SendInput construction and verify test harness stability**

In `tests/test_injector.py`:
- Protect `test_injector_types_vietnamese_into_real_text_window` against host Tkinter installation corruption: wrap `tk.Tk()` in `try ... except (tk.TclError, Exception) as e: pytest.skip(f"Tkinter unavailable: {e}")`.
- Add test verifying `events` array structure and exact event count for multi-character inputs.

- [ ] **Step 2: Run tests to verify**

Run: `python -m pytest tests/test_injector.py -v`

- [ ] **Step 3: Implement direct-indexed `INPUT` construction in `src/injector.py`**

- Calculate total events: `num_units = len(units) // 2`, `total_events = num_units * 2`.
- Allocate ctypes array directly: `events = (INPUT * total_events)()`.
- Iterate through UTF-16 code units with loop index and assign `events[idx]` directly instead of unpacking generator with `*(...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_injector.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/injector.py tests/test_injector.py
git commit -m "fix(injector): use direct array indexing for SendInput events"
```

---

### Task 4: Fix 64-bit Win32 Types, Error Timer Race, and Type Annotations in `OverlayIndicator` (`src/overlay.py`)

**Files:**
- Modify: `src/overlay.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Consumes: `ctypes.windll.user32`, `wintypes`
- Produces: Type-safe `OverlayIndicator` with correct 64-bit HWND handling and queue-bound error versioning

- [ ] **Step 1: Write test for error version forwarding in queue**

In `tests/test_overlay.py`:
- Test that consecutive calls to `show_error("err1")` and `show_error("err2")` pass distinct version tags in `_queue`, preventing the first timer from closing the second error.

- [ ] **Step 2: Run test to verify failure/baseline**

Run: `python -m pytest tests/test_overlay.py -v`

- [ ] **Step 3: Implement Win32 64-bit API setup and queue versioning in `src/overlay.py`**

- Configure `ctypes.windll.user32` functions with 64-bit signatures:
  - `GetParent`: `argtypes = [wintypes.HWND]`, `restype = wintypes.HWND`
  - `ShowWindow`: `argtypes = [wintypes.HWND, ctypes.c_int]`, `restype = wintypes.BOOL`
  - Use `GetWindowLongPtrW` / `SetWindowLongPtrW` (with fallback to `GetWindowLongW`/`SetWindowLongW` on 32-bit):
    `restype = ctypes.c_ssize_t` / `LONG_PTR`, `argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]`.
- Change queue error tuple to `("ERROR", (message, version))`.
- Update `_render_error(self, payload: Tuple[str, int]) -> None` to unpack `message, version` and pass `version` to `after()`.
- Add explicit type hints to all methods (`_hide_if_error(self, version: int) -> None`, `show_error(self, message: str) -> None`, etc.).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/overlay.py tests/test_overlay.py
git commit -m "fix(overlay): configure 64-bit ctypes window APIs and eliminate error timer race"
```

---

### Task 5: Decouple Keyboard Hook Thread from Audio Processing and Injection in `VoiceToWordApp` (`src/main.py`)

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_integration.py`, `tests/test_stability.py`

**Interfaces:**
- Consumes: `AudioRecorder`, `Transcriber`, `TextInjector`, `OverlayIndicator`
- Produces: Non-blocking `on_hotkey_release` (< 5ms execution) and minimal critical-section `_state_lock`

- [ ] **Step 1: Write test verifying hotkey release returns immediately and offloads work to worker**

In `tests/test_stability.py`:
- Test that `on_hotkey_release()` returns immediately without blocking while audio stop and transcription happen in worker thread.
- Test that pressing hotkey during text injection does not block or deadlock.

- [ ] **Step 2: Run test to verify behavior**

Run: `python -m pytest tests/test_stability.py -k "hotkey" -v`

- [ ] **Step 3: Implement asynchronous audio shutdown and scoped locking in `src/main.py`**

- In `on_hotkey_release()`:
  - Under `_state_lock`: verify state, mark `self._recording = False`, mark `self._busy = True`.
  - Dispatch a background thread immediately to execute `_finalize_recording()`:
    - Calls `recorder.stop()`.
    - Evaluates duration and silence.
    - If valid, sets overlay to processing and invokes `_process_and_inject(audio_buffer)`.
    - If invalid or error, resets `self._busy = False` and hides/shows error on overlay.
  - Return immediately from `on_hotkey_release()` so the pynput `WH_KEYBOARD_LL` hook callback exits in milliseconds.
- In `_process_and_inject()`:
  - Keep `_state_lock` only around state checks (`_stopping`, `_busy`), NOT around `self.injector.paste_text(text)` or Groq API calls.

- [ ] **Step 4: Run all integration and stability tests**

Run: `python -m pytest tests/test_integration.py tests/test_stability.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/main.py tests/test_stability.py
git commit -m "fix(main): decouple keyboard hook thread from audio shutdown and injection"
```

---

### Task 6: Final Verification Across Entire Test Suite

- [ ] **Step 1: Run complete test suite**

Run: `python -m pytest -v`
Expected: 79 passed (or skipped where physical desktop focus / missing Tkinter library applies), 0 failed.

- [ ] **Step 2: Confirm git status and commit hygiene**

Run: `git status`
Verify working tree is clean and all changes are strictly scoped.
