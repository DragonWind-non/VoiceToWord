import pytest

from voicetoword.overlay import OverlayIndicator, OverlayState


def test_overlay_state_enum():
    assert OverlayState.HIDDEN.value == "hidden"
    assert OverlayState.RECORDING.value == "recording"
    assert OverlayState.PROCESSING.value == "processing"
    assert OverlayState.ERROR.value == "error"


def test_overlay_indicator_headless_states():
    # Use headless=True to test logic without opening physical OS window
    indicator = OverlayIndicator(headless=True)
    assert indicator.state == OverlayState.HIDDEN

    indicator.show_recording()
    assert indicator.state == OverlayState.RECORDING

    indicator.show_processing()
    assert indicator.state == OverlayState.PROCESSING

    indicator.show_error("API Error")
    assert indicator.state == OverlayState.ERROR
    assert indicator.last_error == "API Error"

    indicator.hide()
    assert indicator.state == OverlayState.HIDDEN


def test_old_error_timeout_does_not_hide_new_recording():
    from unittest.mock import MagicMock

    indicator = OverlayIndicator(headless=True)
    indicator.headless = False
    indicator._root = MagicMock()
    indicator._label = MagicMock()
    indicator._root.after.side_effect = lambda delay, callback: setattr(indicator, "timeout", callback)
    indicator._show_no_activate = lambda: None

    indicator._render_error("network failure")
    indicator.show_recording()
    indicator.timeout()

    assert indicator.state == OverlayState.RECORDING
    indicator._root.withdraw.assert_not_called()


def test_old_error_timeout_does_not_hide_newer_error():
    from unittest.mock import MagicMock

    indicator = OverlayIndicator(headless=True)
    indicator.headless = False
    indicator._root = MagicMock()
    indicator._label = MagicMock()
    callbacks = []
    indicator._root.after.side_effect = lambda delay, callback: callbacks.append(callback)
    indicator._show_no_activate = lambda: None

    indicator.show_error("first")
    indicator._render_error("first")
    indicator.show_error("second")
    indicator._render_error("second")
    callbacks[0]()

    assert indicator.state == OverlayState.ERROR
    indicator._root.withdraw.assert_not_called()


def test_error_queue_carries_version_tuple():
    indicator = OverlayIndicator(headless=True)
    indicator.headless = False
    indicator.show_error("e1")
    indicator.show_error("e2")
    action1, payload1 = indicator._queue.get_nowait()
    action2, payload2 = indicator._queue.get_nowait()
    assert action1 == "ERROR" and payload1 == ("e1", 1)
    assert action2 == "ERROR" and payload2 == ("e2", 2)


def test_clear_result_uses_gui_queue_without_changing_badge_state():
    indicator = OverlayIndicator(headless=True)
    indicator.headless = False
    indicator.show_recording()
    indicator._queue.get_nowait()
    indicator.clear_result()
    assert indicator._queue.get_nowait() == ("CLEAR_RESULT", None)
    assert indicator.state == OverlayState.RECORDING


def test_clear_result_destroys_viewer_and_releases_reference():
    from unittest.mock import MagicMock

    indicator = OverlayIndicator(headless=True)
    window = MagicMock()
    indicator._result_window = window
    indicator._render_clear_result()
    window.destroy.assert_called_once_with()
    assert indicator._result_window is None
    indicator._render_clear_result()


def test_clear_result_tolerates_manually_closed_viewer():
    from unittest.mock import MagicMock

    indicator = OverlayIndicator(headless=True)
    window = MagicMock()
    window.winfo_exists.return_value = False
    indicator._result_window = window
    indicator._render_clear_result()
    window.destroy.assert_not_called()
    assert indicator._result_window is None


def test_real_result_clear_runs_on_gui_thread_and_allows_reopening():
    import queue
    import sys
    import threading
    if sys.platform != "win32":
        pytest.skip("Windows desktop overlay")
    indicator = OverlayIndicator()
    observations = queue.Queue()
    render = indicator._render_result
    clear = indicator._render_clear_result

    def observe_result(text):
        render(text)
        window = indicator._result_window
        box = next(child for child in window.winfo_children() if child.winfo_class() == "Text")
        observations.put(("opened", box.get("1.0", "end-1c")))

    def observe_clear():
        window = indicator._result_window
        clear()
        if window is not None:
            observations.put(("cleared", window.winfo_exists(), indicator._result_window,
                              threading.get_ident() == indicator._thread.ident))

    indicator._render_result = observe_result
    indicator._render_clear_result = observe_clear
    try:
        for text in ("Kết quả cũ. 👋", "Kết quả mới."):
            indicator.show_result(text)
            assert observations.get(timeout=3) == ("opened", text)
            indicator.clear_result()
            assert observations.get(timeout=3) == ("cleared", 0, None, True)
    finally:
        indicator.stop()
    assert not indicator._thread.is_alive()



def test_real_gui_shutdown_releases_tk_on_its_own_thread():
    import sys
    import time
    if sys.platform != "win32":
        pytest.skip("Windows desktop overlay")
    indicator = OverlayIndicator()
    deadline = time.monotonic() + 3
    while indicator._root is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert indicator._root is not None
    indicator.stop()
    assert not indicator._thread.is_alive()
    assert indicator._root is None
    assert indicator._label is None


def test_result_window_keeps_exact_unicode_and_replaces_previous_viewer():
    import queue
    import sys
    if sys.platform != "win32":
        pytest.skip("Windows desktop overlay")
    indicator = OverlayIndicator()
    observations = queue.Queue()
    render = indicator._render_result

    def observe(text):
        render(text)
        window = indicator._result_window
        box = next(child for child in window.winfo_children() if child.winfo_class() == "Text")
        box.event_generate("<<SelectAll>>")
        observations.put((box.get("1.0", "end-1c"), box.cget("state"),
                          box.get("sel.first", "sel.last"),
                          sum(child.winfo_class() == "Toplevel" for child in indicator._root.winfo_children())))

    indicator._render_result = observe
    try:
        for text in ("Kết quả chưa nhập. 👋\nTiếng Việt", "Kết quả tiếp theo."):
            indicator.show_result(text)
            assert observations.get(timeout=3) == (text, "disabled", text, 1)
    finally:
        indicator.stop()
    assert not indicator._thread.is_alive()
    assert indicator._result_window is None


def test_visible_overlay_keeps_noactivate_style_and_foreground_window():
    import ctypes
    import queue
    import sys
    if sys.platform != "win32":
        pytest.skip("Windows desktop overlay")
    indicator = OverlayIndicator()
    observations = queue.Queue()
    show = indicator._show_no_activate
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p

    def observe():
        before = user32.GetForegroundWindow()
        show()
        hwnd = user32.GetParent(indicator._root.winfo_id()) or indicator._root.winfo_id()
        observations.put((bool(user32.GetWindowLongPtrW(hwnd, -20) & 0x08000000),
                          user32.GetForegroundWindow() == before))

    indicator._show_no_activate = observe
    try:
        indicator.show_recording()
        assert observations.get(timeout=3) == (True, True)
        indicator.hide()
        indicator.show_processing()
        assert observations.get(timeout=3) == (True, True)
    finally:
        indicator.stop()
