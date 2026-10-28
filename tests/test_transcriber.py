import io
from unittest.mock import MagicMock

import pytest

from voicetoword.config import Config
from voicetoword.transcriber import TranscribeError, Transcriber, clean_transcription


def test_clean_transcription_cli_commands():
    assert clean_transcription("git status.") == "git status"
    assert clean_transcription("docker ps -a.") == "docker ps -a"
    assert clean_transcription("npm run dev.") == "npm run dev"
    assert clean_transcription("python -m pytest.") == "python -m pytest"
    assert clean_transcription("cd /var/log.") == "cd /var/log"
    assert clean_transcription("cd ..") == "cd .."
    assert clean_transcription("cd ../..") == "cd ../.."
    assert clean_transcription("dir.") == "dir"
    assert clean_transcription("cls.") == "cls"
    assert clean_transcription("go run main.go.") == "go run main.go"
    assert clean_transcription("code .") == "code ."
    assert clean_transcription("cat file.txt.") == "cat file.txt"


def test_clean_transcription_regular_sentences():
    assert clean_transcription("Xin chào mọi người.") == "Xin chào mọi người."
    assert clean_transcription("Hôm nay trời đẹp không?") == "Hôm nay trời đẹp không?"
    assert clean_transcription("   đoạn văn bản có khoảng trắng   ") == "đoạn văn bản có khoảng trắng"
    assert clean_transcription("Direction is important.") == "Direction is important."
    assert clean_transcription("Clear the table.") == "Clear the table."
    assert clean_transcription("Go to the store.") == "Go to the store."
    assert clean_transcription("Code of conduct.") == "Code of conduct."
    assert clean_transcription("Cat is sleeping.") == "Cat is sleeping."
    assert clean_transcription("Exit through the front door.") == "Exit through the front door."


def test_transcribe_handles_segments_with_missing_or_none_text():
    config = Config(groq_api_key="test-key")
    transcriber = Transcriber(config)
    mock_client = MagicMock()
    mock_transcription = MagicMock()
    mock_transcription.text = "fallback text"
    mock_transcription.segments = [
        {"no_speech_prob": None, "avg_logprob": None},
        {"no_speech_prob": 0.01, "avg_logprob": -0.1},
        {"text": None, "no_speech_prob": 0.01, "avg_logprob": -0.1},
        {"text": "valid command", "no_speech_prob": 0.01, "avg_logprob": -0.1},
    ]
    mock_client.audio.transcriptions.create.return_value = mock_transcription
    transcriber._client = mock_client

    buffer = io.BytesIO(b"fake wav data")
    buffer.name = "audio.wav"
    result = transcriber.transcribe(buffer)
    assert result == "fallback text"



def test_transcriber_requires_valid_key():
    config = Config(groq_api_key="")
    transcriber = Transcriber(config)
    with pytest.raises(TranscribeError, match="GROQ_API_KEY is not configured"):
        transcriber.transcribe(io.BytesIO(b"dummy"))


def test_client_cannot_redirect_credentials_via_environment(monkeypatch):
    monkeypatch.setenv("GROQ_BASE_URL", "https://example.invalid")
    transcriber = Transcriber(Config(groq_api_key="test-key"))
    try:
        client = transcriber._get_client()
        assert str(client.base_url).rstrip("/") == "https://api.groq.com"
        assert client.max_retries == 0
        assert transcriber._get_client() is client
    finally:
        if transcriber._client:
            transcriber._client.close()


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

    with pytest.raises(TranscribeError, match="Groq API Error"):
        transcriber.transcribe(buffer)
