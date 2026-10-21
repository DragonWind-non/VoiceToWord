import io
import time
from unittest.mock import MagicMock
import pytest
from src.config import Config
from src.main import VoiceToWordApp
from src.overlay import OverlayState
from src.transcriber import TranscribeError


def test_app_lifecycle_success():
    config = Config(groq_api_key="test-key", min_duration=0.3)

    mock_recorder = MagicMock()
    mock_transcriber = MagicMock()
    mock_injector = MagicMock()

    app = VoiceToWordApp(
        config=config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
        injector=mock_injector,
        headless=True,
    )

    # 1. User presses Right Ctrl
    app.on_hotkey_press()
    mock_recorder.start.assert_called_once()
    assert app.overlay.state == OverlayState.RECORDING

    # 2. User releases Right Ctrl after speaking (duration = 1.0s)
    mock_buffer = io.BytesIO(b"audio_bytes")
    mock_recorder.stop.return_value = (mock_buffer, 1.0)
    mock_transcriber.transcribe.return_value = "git status"

    app.on_hotkey_release()

    # Wait briefly for transcription background thread
    time.sleep(0.1)

    mock_transcriber.transcribe.assert_called_once_with(mock_buffer)
    mock_injector.paste_text.assert_called_once_with("git status")
    assert app.overlay.state == OverlayState.HIDDEN


def test_app_debounce_under_min_duration():
    config = Config(groq_api_key="test-key", min_duration=0.3)

    mock_recorder = MagicMock()
    mock_transcriber = MagicMock()
    mock_injector = MagicMock()

    app = VoiceToWordApp(
        config=config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
        injector=mock_injector,
        headless=True,
    )

    app.on_hotkey_press()
    assert app.overlay.state == OverlayState.RECORDING

    # Key released in 0.1s (accidental tap < 0.3s)
    mock_recorder.stop.return_value = (io.BytesIO(b""), 0.1)

    app.on_hotkey_release()
    time.sleep(0.05)

    mock_transcriber.transcribe.assert_not_called()
    mock_injector.paste_text.assert_not_called()
    assert app.overlay.state == OverlayState.HIDDEN


def test_app_handles_transcription_error():
    config = Config(groq_api_key="test-key", min_duration=0.3)

    mock_recorder = MagicMock()
    mock_transcriber = MagicMock()
    mock_injector = MagicMock()

    mock_transcriber.transcribe.side_effect = TranscribeError("Network unreachable")

    app = VoiceToWordApp(
        config=config,
        recorder=mock_recorder,
        transcriber=mock_transcriber,
        injector=mock_injector,
        headless=True,
    )

    app.on_hotkey_press()
    mock_recorder.stop.return_value = (io.BytesIO(b"data"), 1.0)

    app.on_hotkey_release()
    time.sleep(0.1)

    assert app.overlay.state == OverlayState.ERROR
    assert "Network unreachable" in app.overlay.last_error
    mock_injector.paste_text.assert_not_called()
