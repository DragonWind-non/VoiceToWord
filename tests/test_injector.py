import ctypes
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from voicetoword.injector import TextInjector


@pytest.mark.desktop_input
@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop input only")
@pytest.mark.parametrize("text", [
    "Đây là đoạn nói thử nghiệm bằng tiếng Việt. OpenAI",
    "new titan serum system",
    "Xin chào OpenAI, thử git status.",
    "Tie\u0302\u0301ng Vie\u0323\u0302t",
    "Xin chào 👋 — tiếng Việt 😀",
])
def test_injector_types_vietnamese_into_real_text_window(text):
    import time
    import tkinter as tk

    try:
        root = tk.Tk()
    except (tk.TclError, Exception) as e:
        pytest.skip(f"Tkinter unavailable on this host: {e}")
    root.title("VoiceToWord Unicode test")
    try:
        box = tk.Text(root)
        box.pack()
        root.update()
        root.lift()
        box.focus_force()
        root.update()
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = (ctypes.c_void_p,)
        user32.GetParent.restype = ctypes.c_void_p
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        user32.GetAncestor.restype = ctypes.c_void_p
        user32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)
        hwnd = user32.GetAncestor(root.winfo_id(), 2) or root.winfo_id()
        user32.SetForegroundWindow(hwnd)
        box.focus_force()
        deadline = time.monotonic() + 1
        while user32.GetForegroundWindow() != hwnd and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        if user32.GetForegroundWindow() != hwnd:
            pytest.skip("Desktop session did not grant test window foreground focus")

        for _ in range(4):
            box.delete("1.0", "end")
            assert user32.GetForegroundWindow() == hwnd, "Test window lost foreground before injection"
            assert TextInjector().paste_text(text)
            deadline = time.monotonic() + 1
            while box.get("1.0", "end-1c") != text and time.monotonic() < deadline:
                root.update()
                time.sleep(0.01)
            assert box.get("1.0", "end-1c") == text
    finally:
        root.destroy()


def test_injector_flattens_control_whitespace(monkeypatch):
    import voicetoword.injector as module

    observed = []

    def capture(count, events, size):
        observed.extend(events[i].value.ki.wScan for i in range(0, count, 2))
        return count

    monkeypatch.setattr(module.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(SendInput=capture)))

    assert TextInjector().paste_text("git status\nrm -rf /\tmore")
    assert bytes(byte for unit in observed for byte in (unit & 0xff, unit >> 8)).decode("utf-16le") == "git status rm -rf / more"


def test_injector_skips_empty_text(monkeypatch):
    send = MagicMock()
    import voicetoword.injector as module
    monkeypatch.setattr(module.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(SendInput=send)))

    assert TextInjector().paste_text("") is False
    assert TextInjector().paste_text("   ") is False
    send.assert_not_called()


def test_injector_reports_typing_failure(monkeypatch):
    import voicetoword.injector as module
    monkeypatch.setattr(module.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(SendInput=lambda *args: 0)))

    assert TextInjector().paste_text("text") is False


def test_injector_does_not_send_backspace_escape_or_null(monkeypatch):
    import voicetoword.injector as module
    scans = []
    def capture(count, events, size):
        scans.extend(events[i].value.ki.wScan for i in range(0, count, 2))
        return count
    monkeypatch.setattr(module.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(SendInput=capture)))
    assert TextInjector().paste_text("one\b\x1b\x00two\x7fthree")
    assert scans == [ord(char) for char in "one two three"]


def test_injector_rejects_invalid_unicode_without_sending(monkeypatch):
    import voicetoword.injector as module
    send = MagicMock()
    monkeypatch.setattr(module.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(SendInput=send)))
    assert TextInjector().paste_text("invalid \ud800") is False
    send.assert_not_called()


def native_edit_api(monkeypatch, control="RichEditD2DPT", delivered=1, focuses=(777, 777)):
    import voicetoword.injector as module
    focus_values = iter(focuses)
    inserted = []
    caret = 0

    def gui_info(thread, pointer):
        info = ctypes.cast(pointer, ctypes.POINTER(module.GUITHREADINFO)).contents
        info.hwndFocus = next(focus_values)
        return 1

    def class_name(hwnd, buffer, size):
        buffer.value = control
        return len(control)

    def replace(hwnd, message, undoable, pointer, flags, timeout, result):
        nonlocal caret
        assert hwnd == 777
        assert flags & 2 and timeout <= 1000
        if message == 0xC2:
            assert undoable == 1
            text = ctypes.wstring_at(pointer)
            inserted.append(text)
            caret += len(text.encode("utf-16le")) // 2
        elif message == 0xB0:
            ctypes.cast(undoable, ctypes.POINTER(ctypes.wintypes.DWORD)).contents.value = caret
            ctypes.cast(pointer, ctypes.POINTER(ctypes.wintypes.DWORD)).contents.value = caret
        ctypes.cast(result, ctypes.POINTER(ctypes.c_size_t)).contents.value = 1000000 if message == 0xD5 else caret
        return delivered

    api = SimpleNamespace(
        GetGUIThreadInfo=MagicMock(side_effect=gui_info),
        GetClassNameW=MagicMock(side_effect=class_name),
        IsWindowUnicode=MagicMock(return_value=1),
        GetWindowLongW=MagicMock(return_value=0),
        SendMessageTimeoutW=MagicMock(side_effect=replace),
        SendInput=MagicMock(side_effect=lambda count, events, size: count),
    )
    monkeypatch.setattr(module.ctypes, "windll", SimpleNamespace(user32=api))
    return api, inserted


def test_native_rich_edit_receives_exact_unicode_without_keyboard_packets(monkeypatch):
    api, inserted = native_edit_api(monkeypatch)
    assert TextInjector().paste_text("Xin chào 👋")
    assert inserted == ["Xin chào 👋"]
    api.SendInput.assert_not_called()


def test_native_edit_timeout_does_not_retry_as_keyboard_input(monkeypatch):
    api, inserted = native_edit_api(monkeypatch, delivered=0)
    assert TextInjector().paste_text("Xin chào") is False
    api.SendInput.assert_not_called()


def test_native_edit_focus_change_does_not_type_into_old_or_new_window(monkeypatch):
    api, inserted = native_edit_api(monkeypatch, focuses=(777, 778))
    assert TextInjector().paste_text("Xin chào") is False
    assert inserted == []
    api.SendInput.assert_not_called()


def test_other_controls_keep_unicode_keyboard_input(monkeypatch):
    api, inserted = native_edit_api(monkeypatch, control="Chrome_RenderWidgetHostHWND")
    assert TextInjector().paste_text("Xin chào")
    assert inserted == []
    api.SendInput.assert_called_once()


def test_injector_sendinput_events_indexed_correctly(monkeypatch):
    import voicetoword.injector as module

    captured = []

    def capture(count, events, size):
        for i in range(count):
            captured.append((events[i].value.ki.wScan, events[i].value.ki.dwFlags))
        return count

    monkeypatch.setattr(module.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(SendInput=capture)))
    injector = TextInjector()
    # "AB" -> 2 UTF-16 code units -> 4 events (KeyDown, KeyUp for each)
    assert injector.paste_text("AB")
    assert len(captured) == 4
    # Event 0: 'A' down (0x0004), Event 1: 'A' up (0x0004 | 0x0002)
    assert captured[0] == (ord("A"), 0x0004)
    assert captured[1] == (ord("A"), 0x0004 | 0x0002)
    assert captured[2] == (ord("B"), 0x0004)
    assert captured[3] == (ord("B"), 0x0004 | 0x0002)

