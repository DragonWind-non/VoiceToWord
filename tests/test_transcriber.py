import io
from unittest.mock import MagicMock
import pytest
from src.config import Config
from src.transcriber import Transcriber, TranscribeError, clean_transcription


def test_clean_transcription_cli_commands():
    assert clean_transcription("git status.") == "git status"
    assert clean_transcription("docker ps -a.") == "docker ps -a"
    assert clean_transcription("npm run dev.") == "npm run dev"
    assert clean_transcription("python -m pytest.") == "python -m pytest"
    assert clean_transcription("cd /var/log.") == "cd /var/log"
    assert clean_transcription("dir.") == "dir"
    assert clean_transcription("cls.") == "cls"


def test_clean_transcription_regular_sentences():
    assert clean_transcription("Xin chào mọi người.") == "Xin chào mọi người."
    assert clean_transcription("Hôm nay trời đẹp không?") == "Hôm nay trời đẹp không?"
    assert clean_transcription("   đoạn văn bản có khoảng trắng   ") == "đoạn văn bản có khoảng trắng"


def test_transcriber_requires_valid_key():
    config = Config(groq_api_key="")
    transcriber = Transcriber(config)
    with pytest.raises(TranscribeError, match="GROQ_API_KEY is not configured"):
        transcriber.transcribe(io.BytesIO(b"dummy"))


def test_transcriber_success(monkeypatch):
    config = Config(groq_api_key="test-key", model_name="whisper-large-v3-turbo", language="vi")
    transcriber = Transcriber(config)

    # Mock groq client
    mock_client = MagicMock()
    mock_transcription = MagicMock()
    mock_transcription.text = "git commit -m 'Initial commit'."
    mock_client.audio.transcriptions.create.return_value = mock_transcription
    transcriber._client = mock_client

    buffer = io.BytesIO(b"fake wav data")
    buffer.name = "audio.wav"

    result = transcriber.transcribe(buffer)
    assert result == "git commit -m 'Initial commit'"
    mock_client.audio.transcriptions.create.assert_called_once()


def test_transcriber_api_error():
    config = Config(groq_api_key="test-key")
    transcriber = Transcriber(config)

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = Exception("Connection timed out")
    transcriber._client = mock_client

    buffer = io.BytesIO(b"fake wav data")
    buffer.name = "audio.wav"

    with pytest.raises(TranscribeError, match="Groq API Error: Connection timed out"):
        transcriber.transcribe(buffer)
