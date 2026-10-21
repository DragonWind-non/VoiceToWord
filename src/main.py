import io
import logging
import threading
import time
from typing import Optional

from src.audio_recorder import AudioRecorder
from src.config import Config, load_config
from src.hotkey_listener import HotkeyListener
from src.injector import TextInjector
from src.overlay import OverlayIndicator
from src.transcriber import Transcriber, TranscribeError
from src.tray import TrayManager


log = logging.getLogger(__name__)


class VoiceToWordApp:
    """Main application orchestrating hotkeys, recording, transcription, overlay, and injection."""

    def __init__(
        self,
        config: Optional[Config] = None,
        recorder: Optional[AudioRecorder] = None,
        transcriber: Optional[Transcriber] = None,
        injector: Optional[TextInjector] = None,
        overlay: Optional[OverlayIndicator] = None,
        tray: Optional[TrayManager] = None,
        headless: bool = False,
    ):
        self.config = config or load_config()
        self.recorder = recorder or AudioRecorder(sample_rate=self.config.sample_rate)
        self.transcriber = transcriber or Transcriber(config=self.config)
        self.injector = injector or TextInjector()
        self.overlay = overlay or OverlayIndicator(headless=headless)
        self.tray = tray or TrayManager(on_exit=self.stop)
        self.headless = headless

        self.hotkey_listener = HotkeyListener(
            target_key=self.config.hotkey,
            on_press=self.on_hotkey_press,
            on_release=self.on_hotkey_release,
        )

        self._is_running = False
        self._busy = False
        self._recording = False
        self._state_lock = threading.Lock()

    def on_hotkey_press(self) -> None:
        """Triggered when the push-to-talk hotkey is pressed down."""
        with self._state_lock:
            if self._busy or self._recording:
                return
            self._recording = True
        self.overlay.show_recording()
        try:
            self.recorder.start()
        except Exception as e:
            with self._state_lock:
                self._recording = False
            self.overlay.show_error(f"Lỗi Micro: {e}")

    def on_hotkey_release(self) -> None:
        """Triggered when the push-to-talk hotkey is released."""
        with self._state_lock:
            if not self._recording:
                return
            self._recording = False
            self._busy = True
        try:
            audio_buffer, duration = self.recorder.stop()
        except Exception as e:
            with self._state_lock:
                self._busy = False
            self.overlay.show_error(f"Lỗi ghi âm: {e}")
            return

        # Debounce: If user merely tapped the key briefly (< min_duration), cancel
        if duration < self.config.min_duration:
            with self._state_lock:
                self._busy = False
            self.overlay.hide()
            return

        self.overlay.show_processing()

        # Run transcription and injection in a background thread to prevent blocking
        worker = threading.Thread(
            target=self._process_and_inject,
            args=(audio_buffer,),
            daemon=True,
        )
        worker.start()

    def _process_and_inject(self, audio_buffer: io.BytesIO) -> None:
        """Transcribe audio via Groq Whisper and inject text into active cursor."""
        try:
            text = self.transcriber.transcribe(audio_buffer)
            if text:
                if not self.injector.paste_text(text):
                    self.overlay.show_error("Không thể nhập văn bản vào cửa sổ hiện tại")
                    return
            self.overlay.hide()
        except TranscribeError as e:
            log.error("Transcription failed: %s", e)
            self.overlay.show_error(str(e))
        except Exception as e:
            log.error("VoiceToWord processing failed: %s", e)
            self.overlay.show_error(f"Lỗi: {e}")
        finally:
            with self._state_lock:
                self._busy = False

    def start(self) -> None:
        """Start all services (hotkey listener, tray icon, overlay)."""
        self._is_running = True
        self.hotkey_listener.start()

        if not self.headless:
            self.tray.start()

        log.info("VoiceToWord started; hold %s to record", self.config.hotkey)

    def stop(self) -> None:
        """Gracefully stop all services and exit."""
        self._is_running = False
        self.hotkey_listener.stop()
        self.recorder.stop()
        self.overlay.stop()
        self.tray.stop()
        log.info("VoiceToWord stopped")


def notify_missing_key():
    import ctypes
    ctypes.windll.user32.MessageBoxW(
        0, "Copy .env.example to .env and set GROQ_API_KEY before starting.",
        "VoiceToWord - Configuration required", 0x10,
    )


def main():
    config = load_config()
    if not config.is_valid():
        notify_missing_key()
        raise SystemExit("GROQ_API_KEY is missing. Copy .env.example to .env and configure it.")

    app = VoiceToWordApp(config=config)
    app.start()

    # Keep main thread alive
    try:
        while app._is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    main()
