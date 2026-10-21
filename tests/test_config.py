import os
import pytest
from src.config import Config, load_config


def test_load_config_defaults(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("LANGUAGE", raising=False)
    monkeypatch.delenv("HOTKEY", raising=False)
    monkeypatch.delenv("SAMPLE_RATE", raising=False)
    monkeypatch.delenv("MIN_DURATION_SECONDS", raising=False)

    config = load_config()
    assert config.groq_api_key == ""
    assert config.model_name == "whisper-large-v3-turbo"
    assert config.language == "vi"
    assert config.hotkey == "ctrl_r"
    assert config.sample_rate == 16000
    assert config.min_duration == 0.3


def test_load_config_from_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "whisper-large-v3")
    monkeypatch.setenv("LANGUAGE", "en")
    monkeypatch.setenv("HOTKEY", "f8")
    monkeypatch.setenv("SAMPLE_RATE", "44100")
    monkeypatch.setenv("MIN_DURATION_SECONDS", "0.5")

    config = load_config()
    assert config.groq_api_key == "test-key"
    assert config.model_name == "whisper-large-v3"
    assert config.language == "en"
    assert config.hotkey == "f8"
    assert config.sample_rate == 44100
    assert config.min_duration == 0.5


def test_config_is_valid():
    cfg_invalid = Config(groq_api_key="")
    assert not cfg_invalid.is_valid()

    cfg_valid = Config(groq_api_key="valid_key")
    assert cfg_valid.is_valid()
