import io
import time
import wave
from typing import List, Optional, Tuple
import numpy as np
import sounddevice as sd


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_recording = False
        self.frames: List[np.ndarray] = []
        self._start_time: float = 0.0
        self._stream: Optional[sd.InputStream] = None

    def _audio_callback(self, indata, frames_count, time_info, status):
        """Callback from sounddevice InputStream."""
        if self.is_recording:
            # Copy indata to avoid buffer overwrite
            self.frames.append(indata.copy())

    def start(self) -> None:
        """Start recording from default microphone into memory."""
        if self.is_recording:
            return

        self.frames = []
        self.is_recording = True
        self._start_time = time.time()

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            self.is_recording = False
            self._stream = None
            raise RuntimeError(f"Failed to start audio stream: {e}") from e

    def _export_wav_buffer(self) -> Tuple[io.BytesIO, float]:
        """Convert collected frames to an in-memory WAV buffer."""
        if not self.frames:
            buffer = io.BytesIO()
            buffer.name = "audio.wav"
            return buffer, 0.0

        # Concatenate all recorded numpy arrays
        audio_data = np.concatenate(self.frames, axis=0)
        duration = len(audio_data) / self.sample_rate

        wav_buffer = io.BytesIO()
        wav_buffer.name = "audio.wav"

        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 2 bytes = 16-bit PCM
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())

        wav_buffer.seek(0)
        return wav_buffer, duration

    def stop(self) -> Tuple[io.BytesIO, float]:
        """Stop recording and return (in-memory WAV buffer, duration in seconds)."""
        if not self.is_recording:
            return self._export_wav_buffer()

        self.is_recording = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            finally:
                self._stream = None

        return self._export_wav_buffer()
