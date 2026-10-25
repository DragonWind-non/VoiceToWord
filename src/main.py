import io
import ctypes
import logging
import sys
import threading
import time
from typing import Iterator, Optional
from contextlib import contextmanager
from ctypes import wintypes

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
        self.injector = injector or TextInjector(debug_transcript=self.config.debug_transcript)
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
        self._stopping = False
        self._worker_thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()

    def on_hotkey_press(self) -> None:
        """Triggered when the push-to-talk hotkey is pressed down."""
        with self._state_lock:
            if self._stopping or self._busy or self._recording:
                return
            self._recording = True
            try:
                self.recorder.start()
                self.overlay.show_recording()
            except Exception as e:
                self._recording = False
                self.overlay.show_error(f"Lỗi Micro: {e}")

    def on_hotkey_release(self) -> None:
        """Triggered when the push-to-talk hotkey is released."""
        with self._state_lock:
            if self._stopping or not self._recording:
                return
            self._recording = False
            self._busy = True
            try:
                self._worker_thread = threading.Thread(
                    target=self._finalize_recording_and_process,
                    daemon=True,
                )
                self._worker_thread.start()
            except Exception as e:
                self._busy = False
                self.overlay.show_error(f"Lỗi khởi chạy tác vụ: {e}")

    def _finalize_recording_and_process(self) -> None:
        """Background worker: safely stops audio, checks silence, and triggers transcription."""
        try:
            with self._state_lock:
                if self._stopping:
                    self._busy = False
                    return

            audio_buffer, duration = self.recorder.stop()
            if duration < self.config.min_duration or self.recorder.is_silent(self.config.silence_threshold_dbfs):
                with self._state_lock:
                    self._busy = False
                self.overlay.hide()
                log.info("Recording skipped: too short or below silence threshold")
                return

            self.overlay.show_processing()
            self._process_and_inject(audio_buffer)
        except Exception as e:
            with self._state_lock:
                self._busy = False
            self.overlay.show_error(f"Lỗi ghi âm: {e}")

    def _process_and_inject(self, audio_buffer: io.BytesIO) -> None:
        """Transcribe audio via Groq Whisper and inject text into active cursor."""
        try:
            with self._state_lock:
                if self._stopping:
                    return
            text = self.transcriber.transcribe(audio_buffer)
            with self._state_lock:
                if self._stopping:
                    return
            if text:
                if self.config.debug_transcript:
                    log.debug("INJECTOR_INPUT=%r", text)
                # Inject text WITHOUT holding _state_lock across cross-process SendMessageTimeoutW
                if not self.injector.paste_text(text):
                    with self._state_lock:
                        if not self._stopping:
                            self.overlay.show_error("Không thể nhập văn bản vào cửa sổ hiện tại")
                    return
            with self._state_lock:
                if not self._stopping:
                    self.overlay.hide()
        except TranscribeError as e:
            log.error("Transcription failed: %s", e)
            with self._state_lock:
                if not self._stopping:
                    self.overlay.show_error(str(e))
        except Exception as e:
            log.error("VoiceToWord processing failed (%s)", type(e).__name__)
            with self._state_lock:
                if not self._stopping:
                    self.overlay.show_error("Lỗi xử lý; vui lòng thử lại")
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
        with self._state_lock:
            if self._stopping:
                return
            self._stopping = True
            self._recording = False
            self._is_running = False
        for name, service in (("hotkey", self.hotkey_listener), ("microphone", self.recorder),
                              ("overlay", self.overlay), ("tray", self.tray)):
            try:
                service.stop()
            except Exception as e:
                log.warning("Failed to stop %s (%s)", name, type(e).__name__)
        if self._worker_thread is not None and self._worker_thread is not threading.current_thread():
            self._worker_thread.join(timeout=2)
        log.info("VoiceToWord stopped")


@contextmanager
def single_instance() -> Iterator[None]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateMutexW(None, False, "Local\\VoiceToWord")
    if not handle:
        raise RuntimeError("Cannot create VoiceToWord instance guard.")
    try:
        if ctypes.get_last_error() == 183:
            raise RuntimeError("VoiceToWord is already running; exit the existing app first.")
        yield
    finally:
        kernel.CloseHandle(handle)


def notify_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(
        0, message, "VoiceToWord", 0x10,
    )


def notify_missing_key() -> None:
    notify_error("Copy .env.example to .env and set GROQ_API_KEY before starting.")


def main() -> None:
    config = load_config()
    if sys.stderr is not None:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("src").setLevel(logging.DEBUG if config.debug_transcript else logging.INFO)
    if not config.is_valid():
        notify_missing_key()
        raise SystemExit("GROQ_API_KEY is missing. Copy .env.example to .env and configure it.")

    try:
        with single_instance():
            app = VoiceToWordApp(config=config)
            try:
                app.start()
                while app._is_running:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            finally:
                app.stop()
    except RuntimeError as e:
        notify_error(str(e))
        raise SystemExit(str(e)) from None


if __name__ == "__main__":
    main()
