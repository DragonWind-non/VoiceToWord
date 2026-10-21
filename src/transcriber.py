import io
import re
from typing import Optional
from groq import Groq
from src.config import Config


class TranscribeError(Exception):
    """Custom exception raised when transcription fails."""
    pass


CLI_COMMAND_PREFIXES = (
    "git ", "docker ", "npm ", "pnpm ", "yarn ", "pip ", "cd ", "ls ", "dir ",
    "cat ", "python ", "python3 ", "curl ", "kubectl ", "ssh ", "node ", "deno ",
    "bun ", "go ", "cargo ", "rustc ", "code ", "vim ", "nano ", "clear", "cls",
    "dir", "ls", "pwd", "exit"
)


def clean_transcription(text: str) -> str:
    """Clean transcription result, stripping trailing period for CLI commands."""
    if not text:
        return ""

    cleaned = text.strip()
    lower_text = cleaned.lower()

    is_cli = False
    # Check if starts with a known CLI command
    if any(lower_text == prefix.strip() or lower_text.startswith(prefix) for prefix in CLI_COMMAND_PREFIXES):
        is_cli = True
    # Or contains typical command flags (e.g., -a, --help)
    elif re.search(r"\s+-[a-zA-Z0-9]|\s+--[a-zA-Z0-9]", lower_text):
        is_cli = True

    if is_cli and cleaned.endswith("."):
        cleaned = cleaned[:-1].strip()

    return cleaned


class Transcriber:
    def __init__(self, config: Config):
        self.config = config
        self._client: Optional[Groq] = None

    def _get_client(self) -> Groq:
        if self._client is None:
            if not self.config.is_valid():
                raise TranscribeError("GROQ_API_KEY is not configured in .env file.")
            self._client = Groq(api_key=self.config.groq_api_key)
        return self._client

    def transcribe(self, audio_buffer: io.BytesIO) -> str:
        """Send audio buffer to Groq Whisper API and return transcribed text."""
        if not self.config.is_valid():
            raise TranscribeError("GROQ_API_KEY is not configured in .env file.")

        client = self._get_client()

        audio_buffer.seek(0)
        data = audio_buffer.read()
        if not data:
            return ""

        filename = getattr(audio_buffer, "name", "audio.wav") or "audio.wav"

        try:
            # Groq audio transcriptions expects tuple (filename, bytes) or file-like
            transcription = client.audio.transcriptions.create(
                file=(filename, data),
                model=self.config.model_name,
                language=self.config.language,
                temperature=0.0,
            )
            raw_text = getattr(transcription, "text", "") or ""
            return clean_transcription(raw_text)
        except Exception as e:
            raise TranscribeError(f"Groq API Error: {e}") from e
