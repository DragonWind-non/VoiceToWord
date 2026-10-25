import io
import logging
import re
from typing import Optional
from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq
from src.config import Config


log = logging.getLogger(__name__)


class TranscribeError(Exception):
    """Custom exception raised when transcription fails."""
    pass


CLI_COMMAND_PREFIXES = (
    "git ", "docker ", "npm ", "pnpm ", "yarn ", "pip ", "cd ", "ls ", "dir ",
    "python ", "python3 ", "curl ", "kubectl ", "ssh ", "node ", "deno ",
    "bun ", "cargo ", "rustc ", "pytest ", "vim ", "nano ",
)

STANDALONE_CLI_COMMANDS = ("cls", "dir", "ls", "pwd", "exit")

CONTEXTUAL_CLI_PREFIXES = (
    "go run ", "go build ", "go test ", "go get ", "go mod ", "go install ", "go vet ", "go fmt ",
    "code .", "code -",
)


def clean_transcription(text: str) -> str:
    """Clean transcription result, stripping trailing period for CLI commands."""
    if not text:
        return ""

    cleaned = text.strip()
    lower_text = cleaned.lower()

    is_cli = False
    # Check standalone or unambiguous prefix commands
    if any(lower_text.rstrip(".") == cmd for cmd in STANDALONE_CLI_COMMANDS):
        is_cli = True
    elif any(lower_text.startswith(prefix) for prefix in CLI_COMMAND_PREFIXES):
        is_cli = True
    elif any(lower_text.startswith(prefix) for prefix in CONTEXTUAL_CLI_PREFIXES):
        is_cli = True
    elif lower_text.startswith("cat ") and re.search(r"\s+-[a-zA-Z0-9]|\s+--[a-zA-Z0-9]|\.[a-zA-Z0-9]+", lower_text):
        is_cli = True
    # Or contains typical command flags (e.g., -a, --help)
    elif re.search(r"\s+-[a-zA-Z0-9]|\s+--[a-zA-Z0-9]", lower_text):
        is_cli = True

    if is_cli and cleaned.endswith(".") and not cleaned.endswith(" ."):
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
            self._client = Groq(api_key=self.config.groq_api_key, timeout=15.0, max_retries=0)
        return self._client

    def transcribe(self, audio_buffer: io.BytesIO) -> str:
        """Send audio buffer to Groq Whisper API and return transcribed text."""
        if not self.config.is_valid():
            raise TranscribeError("GROQ_API_KEY is not configured in .env file.")

        audio_buffer.seek(0)
        data = audio_buffer.read()
        if not data:
            return ""

        filename = getattr(audio_buffer, "name", "audio.wav") or "audio.wav"

        try:
            client = self._get_client()
            language = {} if self.config.language == "auto" else {"language": self.config.language}
            transcription = client.audio.transcriptions.create(
                file=(filename, data),
                model=self.config.model_name,
                **language,
                temperature=0.0,
                response_format="verbose_json",
            )
            raw_text = getattr(transcription, "text", "") or ""
            if not isinstance(raw_text, str):
                raise TranscribeError("Groq returned an invalid transcript.")
            if self.config.debug_transcript:
                log.debug("GROQ_RAW=%r", raw_text)
            segments = getattr(transcription, "segments", None)
            if isinstance(segments, list) and segments:
                kept = []
                for segment in segments:
                    # Match Whisper's silence rule; never filter by the words themselves.
                    silent = (segment.get("no_speech_prob", 0) > 0.6
                              and segment.get("avg_logprob", 0) < -1.0)
                    if not silent:
                        part = segment.get("text")
                        if isinstance(part, str) and part.strip():
                            kept.append(part.strip())
                if len(kept) != len(segments):
                    raw_text = " ".join(kept)
                log.info("Groq segments=%d skipped_as_no_speech=%d", len(segments), len(segments) - len(kept))
            cleaned = clean_transcription(raw_text)
            if self.config.debug_transcript:
                log.debug("CLEANED=%r", cleaned)
            return cleaned
        except TranscribeError:
            raise
        except (APITimeoutError, TimeoutError) as e:
            raise TranscribeError("Groq request timed out; please try again.") from e
        except APIConnectionError as e:
            raise TranscribeError("Cannot connect to Groq; check your network.") from e
        except APIStatusError as e:
            raise TranscribeError(f"Groq API Error (HTTP {e.status_code}); check key, model or quota.") from e
        except Exception as e:
            raise TranscribeError("Groq API Error; please try again.") from e
