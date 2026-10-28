import io
import logging
import re
from typing import Optional

from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq

from voicetoword.config import Config

log = logging.getLogger(__name__)


class TranscribeError(Exception):
    """Custom exception raised when transcription fails."""
    pass


CLI_COMMAND_PREFIXES = ("cd ", "ls ", "dir ")

STANDALONE_CLI_COMMANDS = ("cls", "dir", "ls", "pwd", "exit")

CONTEXTUAL_CLI_PREFIXES = (
    "git status", "git add ", "git commit ", "git push", "git pull", "git fetch", "git diff",
    "git log", "git checkout ", "git switch ", "git branch", "git merge ", "git clone ",
    "git reset ", "git restore ", "git stash", "git init", "git remote ", "git rebase ",
    "docker ps", "docker run ", "docker build ", "docker compose ", "docker images", "docker logs ",
    "npm run ", "npm install", "npm test", "npm init", "npm ci", "npm start", "npm uninstall ",
    "pnpm run ", "pnpm add ", "pnpm install", "pnpm test", "yarn add ", "yarn install", "yarn run ",
    "pip install ", "pip uninstall ", "pip list", "pip freeze", "pip show ",
    "cargo run", "cargo build", "cargo test", "cargo check", "cargo add ",
    "deno run ", "deno task ", "bun run ", "bun install", "bun add ", "bun test",
    "kubectl get ", "kubectl apply ", "kubectl describe ", "kubectl logs ", "kubectl exec ",
    "go run ", "go build ", "go test ", "go get ", "go mod ", "go install ", "go vet ", "go fmt ",
    "code .",
)


def clean_transcription(text: str) -> str:
    """Clean transcription result, stripping trailing period for CLI commands."""
    if not text:
        return ""

    cleaned = text.strip()
    lower_text = cleaned.lower()

    is_cli = False
    # shortcut: CLI hints do not parse prose; add forms only for confirmed dictation cases.
    if any(lower_text.rstrip(".") == cmd for cmd in STANDALONE_CLI_COMMANDS):
        is_cli = True
    elif any(lower_text.startswith(prefix) for prefix in CLI_COMMAND_PREFIXES):
        is_cli = True
    elif any(re.match(re.escape(prefix.rstrip()) + r"(?=\s|\.?$)", lower_text) for prefix in CONTEXTUAL_CLI_PREFIXES):
        is_cli = True
    elif re.match(r"(?:git|docker|npm|pnpm|yarn|pip|cargo|deno|bun|kubectl|go)\s+-{1,2}[a-z0-9]", lower_text):
        is_cli = True
    elif lower_text.startswith("cat ") and re.search(r"\s+-[a-zA-Z0-9]|\s+--[a-zA-Z0-9]|\.[a-zA-Z0-9]+", lower_text):
        is_cli = True
    elif re.match(r"(?:python3?|node|code|curl|ssh|rustc|pytest|vim|nano)\s+(?:-{1,2}[a-z0-9]|\S*[\\/@:]|\S+\.[a-z0-9]+)", lower_text):
        is_cli = True

    if is_cli and cleaned.endswith(".") and not cleaned.endswith("..") and not cleaned.endswith(" ."):
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
            self._client = Groq(
                api_key=self.config.groq_api_key, base_url="https://api.groq.com",
                timeout=15.0, max_retries=0,
            )
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
                skipped = 0
                incomplete = False
                for segment in segments:
                    # Match Whisper's silence rule; never filter by the words themselves.
                    no_speech = segment.get("no_speech_prob") if isinstance(segment, dict) else getattr(segment, "no_speech_prob", None)
                    avg_log = segment.get("avg_logprob") if isinstance(segment, dict) else getattr(segment, "avg_logprob", None)
                    silent = ((no_speech or 0.0) > 0.6 and (avg_log or 0.0) < -1.0)
                    if silent:
                        skipped += 1
                    else:
                        part = segment.get("text") if isinstance(segment, dict) else getattr(segment, "text", None)
                        if isinstance(part, str) and part.strip():
                            kept.append(part.strip())
                        else:
                            incomplete = True
                if skipped:
                    if incomplete:
                        raise TranscribeError("Groq returned incomplete segment text; please try again.")
                    raw_text = " ".join(kept)
                log.info("Groq segments=%d skipped_as_no_speech=%d", len(segments), skipped)
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
