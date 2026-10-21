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
