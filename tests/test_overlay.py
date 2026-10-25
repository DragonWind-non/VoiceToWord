import pytest
from src.overlay import OverlayState, OverlayIndicator


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



def test_real_gui_shutdown_releases_tk_on_its_own_thread():
    import time
    import sys
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
