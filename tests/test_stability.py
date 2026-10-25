import io
import logging
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
import httpx
from groq import Groq

from src.audio_recorder import AudioRecorder
from src.config import Config, load_config
from src.main import VoiceToWordApp
from src.overlay import OverlayIndicator, OverlayState
from src.transcriber import TranscribeError, Transcriber


def tone(seconds=0.2, amplitude=100):
    samples = np.arange(round(16000 * seconds))
    return (amplitude * np.sin(2 * np.pi * 440 * samples / 16000)).astype(np.int16).reshape(-1, 1)


@pytest.mark.parametrize("data", [
    np.zeros((16000, 1), dtype=np.int16),
    np.full((16000, 1), 1000, dtype=np.int16),
    np.random.default_rng(7).normal(0, 4, (16000, 1)).astype(np.int16),
])
def test_silence_noise_and_dc_offset_are_rejected(data):
    recorder = AudioRecorder()
    recorder.frames = [data]
    assert recorder.is_silent(-60)


def test_quiet_short_speech_is_not_diluted_by_long_silence():
    recorder = AudioRecorder()
    recorder.frames = [np.zeros((48000, 1), dtype=np.int16), tone(amplitude=80)]
    assert not recorder.is_silent(-60)


def test_one_loud_click_is_not_speech():
    recorder = AudioRecorder()
    data = np.zeros((16000, 1), dtype=np.int16)
    data[500] = 32767
    recorder.frames = [data]
    assert recorder.is_silent(-60)


def test_full_scale_int16_energy_does_not_overflow():
    recorder = AudioRecorder()
    recorder.frames = [np.tile(np.array([-32768, 32767], dtype=np.int16), 1600).reshape(-1, 1)]
    assert not recorder.is_silent(-60)


@pytest.mark.parametrize("operation", ["start", "stop"])
def test_stream_is_closed_when_audio_operation_fails(monkeypatch, operation):
    stream = MagicMock()
    stream.start.side_effect = RuntimeError("device unavailable") if operation == "start" else None
    stream.stop.side_effect = RuntimeError("device disconnected") if operation == "stop" else None
    monkeypatch.setattr("src.audio_recorder.sd.InputStream", lambda **kwargs: stream)
    recorder = AudioRecorder()
    with pytest.raises(RuntimeError):
        recorder.start()
        recorder.stop()
    stream.close.assert_called_once()
    assert not recorder.is_recording
    assert recorder._stream is None


def test_overflow_is_reported_instead_of_sending_damaged_audio(monkeypatch):
    monkeypatch.setattr("src.audio_recorder.sd.InputStream", MagicMock())
    recorder = AudioRecorder()
    recorder.start()
    recorder._audio_callback(tone(), 3200, None, SimpleNamespace(input_overflow=True))
    with pytest.raises(RuntimeError, match="overflow"):
        recorder.stop()


def make_app(recorder=None, transcriber=None, injector=None):
    recorder = recorder if recorder is not None else MagicMock()
    if isinstance(recorder, MagicMock):
        recorder.is_silent.return_value = False
        recorder.stop.return_value = (io.BytesIO(b"synthetic"), 1.0)
    return VoiceToWordApp(
        config=Config(groq_api_key="test"), recorder=recorder,
        transcriber=transcriber or MagicMock(), injector=injector or MagicMock(),
        overlay=OverlayIndicator(headless=True), tray=MagicMock(), headless=True,
    )


def test_digital_silence_never_reaches_cloud_or_injector(monkeypatch):
    monkeypatch.setattr("src.audio_recorder.sd.InputStream", MagicMock())
    app = make_app(recorder=AudioRecorder())
    app.on_hotkey_press()
    app.recorder.frames = [np.zeros((16000, 1), dtype=np.int16)]
    app.on_hotkey_release()
    if getattr(app, "_worker_thread", None):
        app._worker_thread.join(timeout=1)
    app.transcriber.transcribe.assert_not_called()
    app.injector.paste_text.assert_not_called()
    assert app.overlay.state == OverlayState.HIDDEN
    assert not app._busy


def test_hotkey_release_returns_immediately_even_if_audio_stop_blocks():
    import time
    stop_entered = threading.Event()
    stop_gate = threading.Event()

    def slow_stop():
        stop_entered.set()
        assert stop_gate.wait(2)
        return (io.BytesIO(b"data"), 1.0)

    recorder = MagicMock()
    recorder.stop.side_effect = slow_stop
    recorder.is_silent.return_value = False
    app = make_app(recorder=recorder)
    app.on_hotkey_press()

    start_time = time.monotonic()
    app.on_hotkey_release()
    elapsed = time.monotonic() - start_time

    assert elapsed < 0.1
    assert stop_entered.wait(1)
    stop_gate.set()
    if getattr(app, "_worker_thread", None):
        app._worker_thread.join(timeout=1)


def test_state_lock_is_not_held_during_text_injection():
    import time
    paste_entered = threading.Event()
    paste_gate = threading.Event()

    def slow_paste(text):
        paste_entered.set()
        assert paste_gate.wait(2)
        return True

    injector = MagicMock()
    injector.paste_text.side_effect = slow_paste
    app = make_app(injector=injector)
    app.on_hotkey_press()
    app.on_hotkey_release()

    assert paste_entered.wait(2)
    start_time = time.monotonic()
    app.on_hotkey_press()
    elapsed = time.monotonic() - start_time
    assert elapsed < 0.05
    assert app.recorder.start.call_count == 1
    paste_gate.set()
    if getattr(app, "_worker_thread", None):
        app._worker_thread.join(timeout=1)



def test_stop_discards_inflight_response():
    entered, release = threading.Event(), threading.Event()
    transcriber = MagicMock()

    def delayed(audio):
        entered.set()
        assert release.wait(3)
        return "late result"

    transcriber.transcribe.side_effect = delayed
    app = make_app(transcriber=transcriber)
    worker = threading.Thread(target=app._process_and_inject, args=(io.BytesIO(),))
    worker.start()
    try:
        assert entered.wait(3)
        app.stop()
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    app.injector.paste_text.assert_not_called()
    app.on_hotkey_press()
    app.recorder.start.assert_not_called()


def test_worker_start_failure_does_not_leave_app_busy(monkeypatch):
    app = make_app()
    monkeypatch.setattr("src.main.threading.Thread", MagicMock(return_value=SimpleNamespace(
        start=MagicMock(side_effect=RuntimeError("no thread")),
    )))
    app.on_hotkey_press()
    app.on_hotkey_release()
    assert not app._busy
    assert app.overlay.state == OverlayState.ERROR
    app.on_hotkey_press()
    assert app.recorder.start.call_count == 2


def test_stop_cleans_other_services_even_if_recorder_raises():
    app = make_app()
    app.recorder.stop.side_effect = RuntimeError("microphone disconnected")
    app.stop()
    assert app.overlay.state == OverlayState.HIDDEN
    app.tray.stop.assert_called_once()
    app.stop()


def transcription(text, segments=None, **config):
    transcriber = Transcriber(Config(groq_api_key="test", **config))
    transcriber._client = MagicMock()
    transcriber._client.audio.transcriptions.create.return_value = SimpleNamespace(
        text=text, segments=segments,
    )
    return transcriber


def test_uncertain_no_speech_advert_is_discarded_without_blacklist():
    transcriber = transcription("Hãy subscribe cho kênh này.", [
        {"text": "Hãy subscribe cho kênh này.", "no_speech_prob": 0.99, "avg_logprob": -1.5},
    ])
    assert transcriber.transcribe(io.BytesIO(b"wav")) == ""
    assert transcriber._client.audio.transcriptions.create.call_args.kwargs["response_format"] == "verbose_json"


def test_confident_real_subscription_sentence_is_preserved():
    text = "Hãy subscribe cho kênh này."
    transcriber = transcription(text, [{"text": text, "no_speech_prob": 0.01, "avg_logprob": -0.1}])
    assert transcriber.transcribe(io.BytesIO(b"wav")) == text


def test_confident_speech_is_kept_even_with_high_no_speech_probability():
    transcriber = transcription("Quiet speech.", [
        {"text": "Quiet speech.", "no_speech_prob": 0.9, "avg_logprob": -0.2},
    ])
    assert transcriber.transcribe(io.BytesIO(b"wav")) == "Quiet speech."


def test_unfiltered_transcript_keeps_original_word_spacing():
    transcriber = transcription("Hello world.", [
        {"text": "Hello", "no_speech_prob": 0, "avg_logprob": -0.1},
        {"text": "world.", "no_speech_prob": 0, "avg_logprob": -0.1},
    ])
    assert transcriber.transcribe(io.BytesIO(b"wav")) == "Hello world."


def test_filtering_silent_segment_preserves_word_boundaries():
    transcriber = transcription("Hello advert world.", [
        {"text": "Hello", "no_speech_prob": 0, "avg_logprob": -0.1},
        {"text": "advert", "no_speech_prob": 0.9, "avg_logprob": -2},
        {"text": "world.", "no_speech_prob": 0, "avg_logprob": -0.1},
    ])
    assert transcriber.transcribe(io.BytesIO(b"wav")) == "Hello world."


def test_only_silent_segments_are_removed():
    transcriber = transcription("Xin chào. Hãy subscribe.", [
        {"text": "Xin chào.", "no_speech_prob": 0.01, "avg_logprob": -0.2},
        {"text": " Hãy subscribe.", "no_speech_prob": 0.95, "avg_logprob": -2.0},
    ])
    assert transcriber.transcribe(io.BytesIO(b"wav")) == "Xin chào."


def test_auto_language_is_omitted_from_request():
    transcriber = transcription("new titan serum system", language="auto")
    assert transcriber.transcribe(io.BytesIO(b"wav")) == "new titan serum system"
    assert "language" not in transcriber._client.audio.transcriptions.create.call_args.kwargs


def test_transcript_logging_is_opt_in_even_at_debug_level(caplog):
    transcriber = transcription("PRIVATE_TRANSCRIPT")
    with caplog.at_level(logging.DEBUG, logger="src.transcriber"):
        assert transcriber.transcribe(io.BytesIO(b"wav")) == "PRIVATE_TRANSCRIPT"
    assert "PRIVATE_TRANSCRIPT" not in caplog.text


def test_enabled_diagnostics_preserve_raw_before_cleaning(caplog):
    transcriber = transcription("  git status.  ", debug_transcript=True)
    with caplog.at_level(logging.DEBUG, logger="src.transcriber"):
        assert transcriber.transcribe(io.BytesIO(b"wav")) == "git status"
    assert repr("  git status.  ") in caplog.text
    assert repr("git status") in caplog.text


def test_api_error_does_not_echo_secret():
    transcriber = transcription("")
    transcriber._client.audio.transcriptions.create.side_effect = RuntimeError("PRIVATE_KEY_SENTINEL")
    with pytest.raises(TranscribeError) as caught:
        transcriber.transcribe(io.BytesIO(b"wav"))
    assert "PRIVATE_KEY_SENTINEL" not in str(caught.value)


@pytest.mark.parametrize("name,value,attribute,expected", [
    ("SAMPLE_RATE", "0", "sample_rate", 16000),
    ("SAMPLE_RATE", "-16000", "sample_rate", 16000),
    ("MIN_DURATION_SECONDS", "nan", "min_duration", 0.3),
    ("MIN_DURATION_SECONDS", "inf", "min_duration", 0.3),
    ("MIN_DURATION_SECONDS", "-1", "min_duration", 0.3),
    ("SILENCE_THRESHOLD_DBFS", "nan", "silence_threshold_dbfs", -60.0),
    ("SILENCE_THRESHOLD_DBFS", "2", "silence_threshold_dbfs", -60.0),
])
def test_invalid_numeric_config_falls_back(monkeypatch, name, value, attribute, expected):
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv(name, value)
    assert getattr(load_config(), attribute) == expected


@pytest.mark.parametrize("failure", ["timeout", "connection", 401, 429, 500])
def test_real_sdk_error_is_private_and_next_request_recovers(failure, caplog):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("PRIVATE_KEY_SENTINEL", request=request)
            if failure == "connection":
                raise httpx.ConnectError("PRIVATE_KEY_SENTINEL", request=request)
            return httpx.Response(failure, json={"error": {"message": "PRIVATE_KEY_SENTINEL"}})
        return httpx.Response(200, json={"text": "Xin chào.", "segments": [
            {"text": "Xin chào.", "no_speech_prob": 0.01, "avg_logprob": -0.2},
            {"text": " Hãy subscribe.", "no_speech_prob": 0.99, "avg_logprob": -2},
        ]})

    transcriber = Transcriber(Config(groq_api_key="test"))
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with Groq(api_key="test", http_client=http_client, max_retries=0) as client:
            transcriber._client = client
            injector = MagicMock(return_value=True)
            app = make_app(transcriber=transcriber, injector=SimpleNamespace(paste_text=injector))
            with caplog.at_level(logging.INFO):
                app._process_and_inject(io.BytesIO(b"wav"))
                assert app.overlay.state == OverlayState.ERROR
                assert not app._busy
                assert "PRIVATE_KEY_SENTINEL" not in app.overlay.last_error
                injector.assert_not_called()
                app._process_and_inject(io.BytesIO(b"wav"))
                injector.assert_called_once_with("Xin chào.")
                assert app.overlay.state == OverlayState.HIDDEN
                assert not app._busy
    assert calls == 2
    assert "PRIVATE_KEY_SENTINEL" not in caplog.text


@pytest.mark.parametrize("existing", [False, True])
def test_single_instance_releases_handle(monkeypatch, existing):
    import src.main as module
    kernel = SimpleNamespace(CreateMutexW=MagicMock(return_value=123), CloseHandle=MagicMock())
    monkeypatch.setattr("ctypes.WinDLL", lambda *args, **kwargs: kernel)
    monkeypatch.setattr("ctypes.get_last_error", lambda: 183 if existing else 0)
    if existing:
        with pytest.raises(RuntimeError, match="already running"):
            with module.single_instance():
                pytest.fail("Duplicate instance entered application")
    else:
        with module.single_instance():
            kernel.CloseHandle.assert_not_called()
    kernel.CloseHandle.assert_called_once_with(123)


def test_single_instance_creation_failure_is_not_ignored(monkeypatch):
    import src.main as module
    kernel = SimpleNamespace(CreateMutexW=MagicMock(return_value=0), CloseHandle=MagicMock())
    monkeypatch.setattr("ctypes.WinDLL", lambda *args, **kwargs: kernel)
    with pytest.raises(RuntimeError):
        with module.single_instance():
            pytest.fail("Failed guard entered application")
    kernel.CloseHandle.assert_not_called()
