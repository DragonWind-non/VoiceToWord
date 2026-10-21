from dataclasses import dataclass
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class Config:
    groq_api_key: str = ""
    model_name: str = "whisper-large-v3-turbo"
    language: str = "vi"
    hotkey: str = "ctrl_r"
    sample_rate: int = 16000
    min_duration: float = 0.3

    def is_valid(self) -> bool:
        """Returns True if minimum required settings (GROQ API KEY) are set."""
        return bool(self.groq_api_key and self.groq_api_key.strip())


def load_config() -> Config:
    """Load configuration from environment variables with sensible defaults."""
    app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    load_dotenv(app_dir / ".env", override=False)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "whisper-large-v3-turbo").strip()
    lang = os.getenv("LANGUAGE", "vi").strip()
    hotkey = os.getenv("HOTKEY", "ctrl_r").strip()

    try:
        sample_rate = int(os.getenv("SAMPLE_RATE", "16000"))
    except ValueError:
        sample_rate = 16000

    try:
        min_duration = float(os.getenv("MIN_DURATION_SECONDS", "0.3"))
    except ValueError:
        min_duration = 0.3

    return Config(
        groq_api_key=api_key,
        model_name=model,
        language=lang,
        hotkey=hotkey,
        sample_rate=sample_rate,
        min_duration=min_duration,
    )
