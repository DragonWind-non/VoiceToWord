import ctypes
import logging
import sys
import time
from contextlib import contextmanager
from ctypes import wintypes
from typing import Iterator

from voicetoword.app import VoiceToWordApp
from voicetoword.config import load_config


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
    logging.getLogger("voicetoword").setLevel(logging.DEBUG if config.debug_transcript else logging.INFO)
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
