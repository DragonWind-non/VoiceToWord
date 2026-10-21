import io
import sys
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

    def on_hotkey_press(self) -> None:
        """Triggered when the push-to-talk hotkey is pressed down."""
        self.overlay.show_recording()
        try:
            self.recorder.start()
        except Exception as e:
            self.overlay.show_error(f"Lỗi Micro: {e}")

    def on_hotkey_release(self) -> None:
        """Triggered when the push-to-talk hotkey is released."""
        try:
            audio_buffer, duration = self.recorder.stop()
        except Exception as e:
            self.overlay.show_error(f"Lỗi ghi âm: {e}")
            return

        # Debounce: If user merely tapped the key briefly (< min_duration), cancel
        if duration < self.config.min_duration:
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
                self.injector.paste_text(text)
            self.overlay.hide()
        except TranscribeError as e:
            print(f"[VoiceToWord] Transcribe error: {e}")
            self.overlay.show_error(str(e))
        except Exception as e:
            print(f"[VoiceToWord] Unexpected error: {e}")
            self.overlay.show_error(f"Lỗi: {e}")

    def start(self) -> None:
        """Start all services (hotkey listener, tray icon, overlay)."""
        self._is_running = True
        self.hotkey_listener.start()

        if not self.headless:
            self.tray.start()

        print(f"[VoiceToWord] Đã khởi động thành công!")
        print(f"[VoiceToWord] - Phím kích hoạt: Giữ phím [{self.config.hotkey.upper()}] để nói")
        print(f"[VoiceToWord] - Mô hình AI: {self.config.model_name}")
        print(f"[VoiceToWord] - Ngôn ngữ: {self.config.language}")
        print(f"[VoiceToWord] - Ứng dụng đang chạy ngầm trong System Tray (khay hệ thống).")

    def stop(self) -> None:
        """Gracefully stop all services and exit."""
        self._is_running = False
        self.hotkey_listener.stop()
        self.recorder.stop()
        self.overlay.stop()
        self.tray.stop()
        print("[VoiceToWord] Đã dừng ứng dụng.")


def main():
    config = load_config()
    if not config.is_valid():
        print("=" * 60)
        print("LƯU Ý QUAN TRỌNG: Bạn chưa cấu hình GROQ_API_KEY!")
        print("Vui lòng mở file .env (hoặc copy từ .env.example) và điền:")
        print("GROQ_API_KEY=test-key")
        print("Lấy key miễn phí trong 10 giây tại: https://console.groq.com/keys")
        print("=" * 60)

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
