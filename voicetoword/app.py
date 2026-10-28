import io
import logging
import threading
from typing import Optional

from voicetoword.audio_recorder import AudioRecorder
from voicetoword.config import Config, load_config
from voicetoword.hotkey_listener import HotkeyListener
from voicetoword.injector import TextInjector
from voicetoword.overlay import OverlayIndicator
from voicetoword.transcriber import TranscribeError, Transcriber
from voicetoword.tray import TrayManager

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
        self.tray = tray or TrayManager(on_exit=self.stop, on_show_result=self.show_pending_result)
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
        self._recording_released = threading.Event()
        self.pending_text = ""

    def on_hotkey_press(self) -> None:
        """Triggered when the push-to-talk hotkey is pressed down."""
        with self._state_lock:
            if self._stopping or self._busy or self._recording:
                return
            self._recording = True
            self._busy = True
            self._recording_released.clear()
            try:
                worker = threading.Thread(target=self._record_and_process, daemon=True)
                worker.start()
                self._worker_thread = worker
            except Exception as e:
                self._recording = False
                self._busy = False
                self._worker_thread = None
                self.overlay.show_error(f"Lỗi khởi chạy tác vụ: {e}")

    def on_hotkey_release(self) -> None:
        """Triggered when the push-to-talk hotkey is released."""
        with self._state_lock:
            if self._stopping or not self._recording:
                return
            self._recording = False
            self._recording_released.set()

    def _record_and_process(self) -> None:
        """Own the microphone for one press/release cycle, including startup and cleanup."""
        started = False
        try:
            with self._state_lock:
                if self._stopping or self._recording_released.is_set():
                    return

            self.recorder.start()
            started = True
            with self._state_lock:
                ready = not self._stopping and not self._recording_released.is_set()
                if ready:
                    self.overlay.show_recording()
            if ready:
                self._recording_released.wait()

            # stop() closes the stream even when it reports an audio error.
            started = False
            audio_buffer, duration = self.recorder.stop()
            with self._state_lock:
                if self._stopping or not ready:
                    return
            if duration < self.config.min_duration or self.recorder.is_silent(self.config.silence_threshold_dbfs):
                self.overlay.hide()
                log.info("Recording skipped: too short or below silence threshold")
                return

            with self._state_lock:
                if self._stopping:
                    return
            self.overlay.show_processing()
            self._process_and_inject(audio_buffer)
        except Exception as e:
            with self._state_lock:
                if not self._stopping:
                    self.overlay.show_error(f"Lỗi ghi âm: {e}")
        finally:
            try:
                if started:
                    self.recorder.stop()
            except Exception as e:
                log.warning("Failed to close microphone (%s)", type(e).__name__)
            finally:
                self.recorder.frames.clear()
                with self._state_lock:
                    self._recording = False
                    self._busy = False

    def show_pending_result(self) -> None:
        with self._state_lock:
            if self._stopping:
                return
            text = self.pending_text
            # Queue the viewer before another thread can invalidate this result.
            if text:
                self.overlay.show_result(text)
            else:
                self.overlay.show_error("Chưa có kết quả cần lấy lại")

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
                    self.pending_text = text
                    self.overlay.clear_result()
            if text:
                if self.config.debug_transcript:
                    log.debug("INJECTOR_INPUT=%r", text)
                # Inject text WITHOUT holding _state_lock across cross-process SendMessageTimeoutW
                if not self.injector.paste_text(text):
                    with self._state_lock:
                        if not self._stopping:
                            self.overlay.show_error("Không nhập được; xem kết quả tại khay hệ thống")
                    return
            with self._state_lock:
                if not self._stopping:
                    if text:
                        self.pending_text = ""
                        self.overlay.clear_result()
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
            self.pending_text = ""
            self.overlay.clear_result()
            self._recording_released.set()
        if self._worker_thread is not None and self._worker_thread is not threading.current_thread():
            self._worker_thread.join(timeout=2)
        services = [("hotkey", self.hotkey_listener), ("overlay", self.overlay), ("tray", self.tray)]
        if self._worker_thread is None:
            services.insert(1, ("microphone", self.recorder))
        for name, service in services:
            try:
                service.stop()
            except Exception as e:
                log.warning("Failed to stop %s (%s)", name, type(e).__name__)
        log.info("VoiceToWord stopped")
