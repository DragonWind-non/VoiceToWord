import io
import time
import wave
import numpy as np
import pytest
from src.audio_recorder import AudioRecorder


def test_audio_recorder_init():
    recorder = AudioRecorder(sample_rate=16000, channels=1)
    assert recorder.sample_rate == 16000
    assert recorder.channels == 1
    assert not recorder.is_recording


def test_audio_recorder_buffer_generation():
    recorder = AudioRecorder(sample_rate=16000, channels=1)

    # Simulate recorded audio frames (0.5 second of 440Hz sine wave)
    duration = 0.5
    t = np.linspace(0, duration, int(16000 * duration), endpoint=False)
    simulated_data = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16).reshape(-1, 1)

    recorder.frames = [simulated_data]
    recorder._start_time = time.time() - duration

    wav_buffer, recorded_duration = recorder._export_wav_buffer()

    assert isinstance(wav_buffer, io.BytesIO)
    assert wav_buffer.getbuffer().nbytes > 44  # WAV header is 44 bytes + data
    assert recorded_duration >= 0.45

    # Verify buffer is readable by standard wave module
    wav_buffer.seek(0)
    with wave.open(wav_buffer, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit PCM
        assert wf.getframerate() == 16000
        assert wf.getnframes() == len(simulated_data)


def test_audio_recorder_empty_recording():
    recorder = AudioRecorder(sample_rate=16000, channels=1)
    wav_buffer, duration = recorder.stop()
    assert duration == 0.0
    assert wav_buffer.getbuffer().nbytes == 0
