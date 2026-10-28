import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    groq_api_key: str = field(default="", repr=False)
    model_name: str = "whisper-large-v3-turbo"
    language: str = "vi"
    hotkey: str = "ctrl_r"
    sample_rate: int = 16000
    min_duration: float = 0.3
    silence_threshold_dbfs: float = -60.0
    debug_transcript: bool = False

    def is_valid(self) -> bool:
        """Returns True if minimum required settings (GROQ API KEY) are set."""
        key = self.groq_api_key.strip()
        return bool(key) and key != "your_groq_api_key_here"


def load_config() -> Config:
    """Load configuration from environment variables with sensible defaults."""
    app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    if not getattr(sys, "frozen", False) and not (app_dir / "run.py").is_file():
        app_dir = Path.cwd()
    load_dotenv(app_dir / ".env", override=False)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "whisper-large-v3-turbo").strip()
    lang = os.getenv("LANGUAGE", "vi").strip().lower() or "vi"
    hotkey = os.getenv("HOTKEY", "ctrl_r").strip()

    try:
        sample_rate = int(os.getenv("SAMPLE_RATE", "16000"))
        if sample_rate <= 0:
            sample_rate = 16000
    except ValueError:
        sample_rate = 16000

    try:
        min_duration = float(os.getenv("MIN_DURATION_SECONDS", "0.3"))
        if not math.isfinite(min_duration) or min_duration < 0:
            min_duration = 0.3
    except ValueError:
        min_duration = 0.3

    try:
        silence_threshold = float(os.getenv("SILENCE_THRESHOLD_DBFS", "-60"))
        if not math.isfinite(silence_threshold) or not -96 <= silence_threshold <= 0:
            silence_threshold = -60.0
    except ValueError:
        silence_threshold = -60.0

    return Config(
        groq_api_key=api_key,
        model_name=model,
        language=lang,
        hotkey=hotkey,
        sample_rate=sample_rate,
        min_duration=min_duration,
        silence_threshold_dbfs=silence_threshold,
        debug_transcript=os.getenv("DEBUG_TRANSCRIPT", "0").strip() == "1",
    )
