import ctypes
import logging
import re
from ctypes import wintypes
from typing import Optional


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("value", INPUT_UNION)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class TextInjector:
    def __init__(self, debug_transcript: bool = False):
        self.debug_transcript = debug_transcript

    def _paste_into_edit_control(self, text: str) -> Optional[bool]:
        user32 = ctypes.windll.user32
        if not hasattr(user32, "GetGUIThreadInfo"):
            return None
        user32.GetGUIThreadInfo.argtypes = (wintypes.DWORD, ctypes.POINTER(GUITHREADINFO))
        user32.GetGUIThreadInfo.restype = wintypes.BOOL
        info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        if not user32.GetGUIThreadInfo(0, ctypes.byref(info)) or not info.hwndFocus:
            return None
        user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        user32.GetClassNameW.restype = ctypes.c_int
        name = ctypes.create_unicode_buffer(256)
        if not user32.GetClassNameW(info.hwndFocus, name, len(name)):
            return None
        control = name.value.lower()
        if control != "edit" and not control.startswith("richedit"):
            return None
        user32.IsWindowUnicode.argtypes = (wintypes.HWND,)
        user32.IsWindowUnicode.restype = wintypes.BOOL
        if not user32.IsWindowUnicode(info.hwndFocus):
            return None
        current = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        if not user32.GetGUIThreadInfo(0, ctypes.byref(current)) or current.hwndFocus != info.hwndFocus:
            return False
        user32.SendMessageTimeoutW.argtypes = (
            wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_void_p,
            wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
        )
        user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
        buffer = ctypes.create_unicode_buffer(text)
        result = ctypes.c_size_t()
        # RichEdit corrupted queued VK_PACKET input in live tests; insert at its caret directly.
        return bool(user32.SendMessageTimeoutW(
            info.hwndFocus, 0xC2, 1, ctypes.cast(buffer, ctypes.c_void_p),
            0x22, 1000, ctypes.byref(result),
        ))

    def paste_text(self, text: str) -> bool:
        """Send Unicode characters in order without touching the clipboard."""
        if not text or not text.strip():
            return False

        # Do not turn untrusted transcript control characters into editing keys.
        text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
        if not text.strip():
            return False
        if self.debug_transcript:
            logging.getLogger(__name__).debug("INJECTOR_FINAL=%r", text)
        try:
            units = text.encode("utf-16le")
        except UnicodeEncodeError:
            return False
        try:
            inserted = self._paste_into_edit_control(text)
        except (AttributeError, OSError):
            return False
        if inserted is not None:
            return inserted
        total_events = len(units)
        events = (INPUT * total_events)()
        idx = 0
        for i in range(0, len(units), 2):
            scan_code = units[i] | (units[i + 1] << 8)
            for flag in (0x0004, 0x0004 | 0x0002):
                events[idx].type = 1
                events[idx].value.ki.wScan = scan_code
                events[idx].value.ki.dwFlags = flag
                idx += 1
        try:
            return ctypes.windll.user32.SendInput(len(events), events, ctypes.sizeof(INPUT)) == len(events)
        except (AttributeError, OSError):
            return False
