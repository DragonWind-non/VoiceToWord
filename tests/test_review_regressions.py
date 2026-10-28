import ctypes
import io
import sys
import threading
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from voicetoword.app import VoiceToWordApp
from voicetoword.audio_recorder import AudioRecorder
from voicetoword.config import Config
from voicetoword.injector import GUITHREADINFO, TextInjector
from voicetoword.overlay import OverlayIndicator
from voicetoword.transcriber import TranscribeError, Transcriber, clean_transcription
from voicetoword.tray import TrayManager


def make_app(**kwargs):
    return VoiceToWordApp(
        config=Config(groq_api_key="test"),
        recorder=kwargs.get("recorder", MagicMock()),
        transcriber=kwargs.get("transcriber", MagicMock()),
        injector=kwargs.get("injector", MagicMock()),
        overlay=kwargs.get("overlay", OverlayIndicator(headless=True)),
        tray=MagicMock(), headless=True,
    )


def test_worker_start_failure_never_leaves_microphone_open(monkeypatch):
    stream = MagicMock()
    monkeypatch.setattr("voicetoword.audio_recorder.sd.InputStream", lambda **kwargs: stream)
    recorder = AudioRecorder()
    app = make_app(recorder=recorder)
    try:
        with patch("voicetoword.app.threading.Thread.start", side_effect=RuntimeError("no thread")):
            app.on_hotkey_press()
            app.on_hotkey_release()
        assert not recorder.is_recording
        assert recorder._stream is None
        assert not app._busy
        app.stop()
    finally:
        # The old implementation leaves an unstarted thread and an open stream.
        app._worker_thread = None
        recorder.stop()


def test_microphone_start_does_not_block_hotkey_and_early_release_discards_audio(monkeypatch):
    entered, proceed, returned = threading.Event(), threading.Event(), threading.Event()
    stream = MagicMock()

    def slow_start():
        entered.set()
        assert proceed.wait(3)

    stream.start.side_effect = slow_start
    monkeypatch.setattr("voicetoword.audio_recorder.sd.InputStream", lambda **kwargs: stream)
    app = make_app(recorder=AudioRecorder())

    def press():
        app.hotkey_listener._handle_press(app.hotkey_listener.target_key)
        returned.set()

    callback = threading.Thread(target=press)
    callback.start()
    try:
        assert entered.wait(2)
        assert returned.wait(0.2), "Microphone initialization blocked the hotkey callback"
        app.hotkey_listener._handle_release(app.hotkey_listener.target_key)
    finally:
        proceed.set()
        callback.join(3)
        app.stop()
    stream.close.assert_called_once()
    app.transcriber.transcribe.assert_not_called()
    assert not app.recorder.is_recording


@pytest.mark.parametrize("segments", [
    [{"no_speech_prob": 0.01, "avg_logprob": -0.1}],
    [{"text": "first clause.", "no_speech_prob": 0.01, "avg_logprob": -0.1},
     {"text": None, "no_speech_prob": 0.01, "avg_logprob": -0.1}],
])
def test_incomplete_segments_keep_full_transcript_when_no_silence_is_filtered(segments):
    transcriber = Transcriber(Config(groq_api_key="test"))
    transcriber._client = MagicMock()
    transcriber._client.audio.transcriptions.create.return_value = SimpleNamespace(
        text="first clause. second clause.", segments=segments,
    )
    assert transcriber.transcribe(io.BytesIO(b"wav")) == "first clause. second clause."


def test_incomplete_segments_fail_explicitly_when_silence_must_be_filtered():
    transcriber = Transcriber(Config(groq_api_key="test"))
    transcriber._client = MagicMock()
    transcriber._client.audio.transcriptions.create.return_value = SimpleNamespace(
        text="real speech. hallucination.", segments=[
            {"text": None, "no_speech_prob": 0.01, "avg_logprob": -0.1},
            {"text": "hallucination.", "no_speech_prob": 0.99, "avg_logprob": -2},
        ],
    )
    with pytest.raises(TranscribeError, match="incomplete segment"):
        transcriber.transcribe(io.BytesIO(b"wav"))


@pytest.mark.parametrize("text", [
    "Python is easy to learn.", "Git is useful.",
    "Please use -v for verbose output.", "Docker rất hữu ích.",
    "Vim is useful.", "Curl is a tool.", "Rustc compiles Rust.",
    "Git statusbar is visible.",
])
def test_cli_cleanup_keeps_ordinary_sentences(text):
    assert clean_transcription(text) == text


@pytest.mark.parametrize("text", [
    "python main.py.", "node server.js.", "vim notes.txt.",
    "curl https://example.com.", "ssh user@host.", "kubectl get pods.",
    "git push.", "code --wait.",
])
def test_cli_cleanup_keeps_recognizing_concrete_commands(text):
    assert clean_transcription(text) == text[:-1]


@pytest.mark.parametrize("tool", [
    "git", "docker", "npm", "pnpm", "yarn", "pip", "cargo", "deno", "bun", "kubectl", "go",
])
@pytest.mark.parametrize("flag", ["--version", "--help", "-v"])
def test_cli_cleanup_recognizes_global_flags(tool, flag):
    assert clean_transcription(f"{tool} {flag}.") == f"{tool} {flag}"


@pytest.mark.parametrize("text", [
    "GitHub --version.", "Docker rất hữu ích.", "npm is a package manager.",
    "Please use -v for verbose output.", "git --version..", "git --help .",
    "code .", "cd ..", "git -.", "git --.",
])
def test_global_flag_cleanup_preserves_prose_and_meaningful_periods(text):
    assert clean_transcription(text) == text


@pytest.mark.parametrize("inserted", [False, True])
def test_new_transcript_invalidates_previous_viewer_before_injection(inserted):
    overlay = MagicMock()
    viewer = {"text": ""}
    overlay.show_result.side_effect = lambda text: viewer.update(text=text)
    overlay.clear_result.side_effect = lambda: viewer.update(text="")
    app = make_app(overlay=overlay)
    app.pending_text = "old failed result"
    app.show_pending_result()
    app.transcriber.transcribe.return_value = "new result"

    def inject(text):
        assert viewer["text"] == ""
        assert app.pending_text == text
        app.show_pending_result()
        return inserted

    app.injector.paste_text.side_effect = inject
    try:
        app._process_and_inject(io.BytesIO(b"wav"))
        assert app.pending_text == ("" if inserted else "new result")
        assert viewer["text"] == app.pending_text
        app.stop()
        assert viewer["text"] == ""
    finally:
        app.stop()


@pytest.mark.parametrize("outcome", ["", TranscribeError("offline")])
def test_empty_or_failed_transcription_preserves_pending_result_and_viewer(outcome):
    overlay = MagicMock()
    app = make_app(overlay=overlay)
    app.pending_text = "recoverable result"
    app.show_pending_result()
    if isinstance(outcome, Exception):
        app.transcriber.transcribe.side_effect = outcome
    else:
        app.transcriber.transcribe.return_value = outcome
    try:
        app._process_and_inject(io.BytesIO(b"wav"))
        assert app.pending_text == "recoverable result"
        overlay.clear_result.assert_not_called()
        app.injector.paste_text.assert_not_called()
    finally:
        app.stop()


@pytest.mark.parametrize("change", ["replace", "success", "stop"])
def test_opening_viewer_cannot_reappear_after_result_is_invalidated(change):
    entered, proceed, changing, finished = (threading.Event() for _ in range(4))
    overlay = MagicMock()
    viewer = {"text": ""}

    def show(text):
        entered.set()
        assert proceed.wait(3)
        viewer["text"] = text

    overlay.show_result.side_effect = show
    overlay.clear_result.side_effect = lambda: viewer.update(text="")
    app = make_app(overlay=overlay)
    app.pending_text = "old result"

    def transcribe(audio):
        changing.set()
        return "new result"

    app.transcriber.transcribe.side_effect = transcribe
    app.injector.paste_text.return_value = change == "success"

    def invalidate():
        changing.set()
        if change == "stop":
            app.stop()
        else:
            app._process_and_inject(io.BytesIO(b"wav"))
        finished.set()

    opener = threading.Thread(target=app.show_pending_result)
    updater = threading.Thread(target=invalidate)
    opener.start()
    try:
        assert entered.wait(2)
        updater.start()
        assert changing.wait(2)
        # Give an incorrectly unlocked update time to overtake the queued viewer.
        finished.wait(0.2)
    finally:
        proceed.set()
        opener.join(3)
        if updater.ident is not None:
            updater.join(3)
    try:
        assert not opener.is_alive() and not updater.is_alive()
        assert viewer["text"] == ""
    finally:
        app.stop()


def test_failed_insertion_can_be_recovered_without_network_or_clipboard():
    transcriber, injector, overlay = MagicMock(), MagicMock(), MagicMock()
    transcriber.transcribe.return_value = "Kết quả cần giữ lại."
    injector.paste_text.return_value = False
    app = make_app(transcriber=transcriber, injector=injector, overlay=overlay)
    app._process_and_inject(io.BytesIO(b"wav"))
    assert app.pending_text == "Kết quả cần giữ lại."
    app.show_pending_result()
    overlay.show_result.assert_called_once_with("Kết quả cần giữ lại.")
    transcriber.transcribe.assert_called_once()
    injector.paste_text.assert_called_once()
    app.stop()
    assert app.pending_text == ""


def test_successful_insertion_clears_pending_result():
    transcriber, injector = MagicMock(), MagicMock()
    transcriber.transcribe.return_value = "new result"
    injector.paste_text.return_value = True
    app = make_app(transcriber=transcriber, injector=injector)
    app.pending_text = "old failed result"
    app._process_and_inject(io.BytesIO(b"wav"))
    assert app.pending_text == ""


def test_tray_result_action_reaches_application_callback():
    show = MagicMock()
    tray = TrayManager(on_show_result=show)
    item = next(item for item in tray._create_menu().items if item.text == "Xem kết quả chưa nhập")
    item(None)
    show.assert_called_once_with()


def test_stop_while_microphone_is_opening_leaves_no_stream_or_upload(monkeypatch):
    entered, proceed = threading.Event(), threading.Event()
    stream = MagicMock()

    def slow_start():
        entered.set()
        assert proceed.wait(3)

    stream.start.side_effect = slow_start
    monkeypatch.setattr("voicetoword.audio_recorder.sd.InputStream", lambda **kwargs: stream)
    app = make_app(recorder=AudioRecorder())
    stopper = threading.Thread(target=app.stop)
    app.on_hotkey_press()
    try:
        assert entered.wait(2)
        stopper.start()
        assert app._recording_released.wait(1)
    finally:
        proceed.set()
        if stopper.ident is not None:
            stopper.join(3)
        else:
            app.stop()
        app._worker_thread.join(3)
    assert not stopper.is_alive() and not app._worker_thread.is_alive()
    assert app.recorder._stream is None
    assert app.recorder.frames == []
    stream.close.assert_called_once()
    app.transcriber.transcribe.assert_not_called()


def test_new_recording_after_worker_failure_contains_only_new_audio(monkeypatch, start_recording):
    import numpy as np

    stream = MagicMock()
    monkeypatch.setattr("voicetoword.audio_recorder.sd.InputStream", lambda **kwargs: stream)
    app = make_app(recorder=AudioRecorder())
    with patch("voicetoword.app.threading.Thread.start", side_effect=RuntimeError("no thread")):
        app.on_hotkey_press()
        app.on_hotkey_release()
    app.recorder._audio_callback(np.full((16000, 1), 5000, dtype=np.int16), 16000, None, None)
    assert app.recorder.frames == []
    start_recording(app)
    samples = (1000 * np.sin(2 * np.pi * 440 * np.arange(8000) / 16000)).astype(np.int16).reshape(-1, 1)
    app.recorder._audio_callback(samples, len(samples), None, None)
    app.transcriber.transcribe.return_value = "new speech"
    app.on_hotkey_release()
    app._worker_thread.join(2)
    app.transcriber.transcribe.assert_called_once()
    import wave
    with wave.open(app.transcriber.transcribe.call_args.args[0], "rb") as wav:
        assert wav.getnframes() == len(samples)


@pytest.fixture
def native_edit(monkeypatch):
    user32 = ctypes.windll.user32
    user32.CreateWindowExW.argtypes = (
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
    )
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = (wintypes.HWND,)
    user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t)
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    windows = []
    _rich_edit_library = ctypes.WinDLL("Msftedit.dll")

    def create(control="Edit", readonly=False, limit=5, initial="", selection=(0, 0)):
        hwnd = user32.CreateWindowExW(
            0, control, initial, 0x80000000 | 0x4 | (0x800 if readonly else 0),
            0, 0, 100, 40, None, None, None, None,
        )
        assert hwnd
        windows.append(hwnd)
        if control == "Edit":
            user32.SendMessageW(hwnd, 0xC5, limit, 0)
        else:
            user32.SendMessageW(hwnd, 0x435, 0, limit)
        user32.SendMessageW(hwnd, 0xB1, *selection)

        def own_focus(thread_id, pointer):
            ctypes.cast(pointer, ctypes.POINTER(GUITHREADINFO)).contents.hwndFocus = hwnd
            return 1

        monkeypatch.setattr(user32, "GetGUIThreadInfo", MagicMock(side_effect=own_focus))

        def content():
            buffer = ctypes.create_unicode_buffer(1024)
            user32.GetWindowTextW(hwnd, buffer, len(buffer))
            return buffer.value

        return content

    yield create
    for hwnd in windows:
        user32.DestroyWindow(hwnd)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows edit controls")
@pytest.mark.parametrize("control", ["Edit", "RICHEDIT50W"])
def test_native_edit_rejects_oversized_text_without_partial_insertion(native_edit, control):
    content = native_edit(control=control)
    assert TextInjector().paste_text("abcdefghij") is False
    assert content() == ""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows edit controls")
@pytest.mark.parametrize("control", ["Edit", "RICHEDIT50W"])
def test_native_edit_does_not_bypass_readonly(native_edit, control):
    content = native_edit(control=control, readonly=True, limit=100)
    assert TextInjector().paste_text("text") is False
    assert content() == ""


@pytest.mark.skipif(sys.platform != "win32", reason="Windows edit controls")
@pytest.mark.parametrize("control", ["Edit", "RICHEDIT50W"])
@pytest.mark.parametrize("initial,selection,text,expected", [
    ("", (0, 0), "ab😀c", "ab😀c"),
    ("abcde", (1, 4), "XY", "aXYe"),
])
def test_native_edit_limit_counts_utf16_and_replaced_selection(native_edit, control, initial, selection, text, expected):
    content = native_edit(control=control, initial=initial, selection=selection)
    assert TextInjector().paste_text(text)
    assert content() == expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows edit controls")
@pytest.mark.parametrize("control,selection", [("Edit", (1, 3)), ("RICHEDIT50W", (1, 2))])
def test_native_edit_replaces_newline_at_exact_capacity(native_edit, control, selection):
    content = native_edit(control=control, initial="a\r\nb", selection=selection, limit=4)
    assert TextInjector().paste_text("XY")
    assert content() == "aXYb"
