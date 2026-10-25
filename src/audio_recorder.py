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
        self._audio_error: str = ""

    def _audio_callback(self, indata, frames_count, time_info, status):
        """Callback from sounddevice InputStream."""
        if self.is_recording:
            if status and getattr(status, "input_overflow", False):
                self._audio_error = "Audio input overflow"
            # Copy indata to avoid buffer overwrite
            self.frames.append(indata.copy())

    def start(self) -> None:
        """Start recording from default microphone into memory."""
        if self.is_recording:
            return

        self.frames = []
        self._audio_error = ""
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
            try:
                if self._stream is not None:
                    self._stream.close()
            finally:
                self._stream = None
            raise RuntimeError(f"Failed to start audio stream: {e}") from e

    def is_silent(self, threshold_dbfs: float = -60.0, data: Optional[np.ndarray] = None) -> bool:
        """Require 100 ms above the noise floor, measured in 20 ms frames."""
        if data is None:
            if not self.frames:
                return True
            data = np.concatenate(self.frames, axis=0)
        elif len(data) == 0:
            return True
        frame_size = max(1, round(self.sample_rate * 0.02))
        active_samples = 0
        threshold_ratio = 10 ** (threshold_dbfs / 20)
        for offset in range(0, len(data), frame_size):
            frame = data[offset:offset + frame_size].astype(np.float32)
            frame = frame - frame.mean(axis=0)
            rms = np.sqrt(np.mean(frame * frame)) / 32768.0
            if rms > threshold_ratio:
                active_samples += len(frame)
        # shortcut: energy cannot distinguish loud background noise from speech; calibrate on the real microphone.
        return active_samples < round(self.sample_rate * 0.1)

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

        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                try:
                    stream.stop()
                finally:
                    stream.close()
            except Exception as e:
                raise RuntimeError(f"Failed to stop audio stream: {e}") from e

        if self._audio_error:
            raise RuntimeError(f"{self._audio_error}; please record again.")

        return self._export_wav_buffer()
