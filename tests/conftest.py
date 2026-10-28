import threading
from unittest.mock import patch

import pytest


@pytest.fixture
def start_recording():
    apps = []

    def start(app):
        apps.append(app)
        ready = threading.Event()
        show_recording = app.overlay.show_recording

        def shown():
            show_recording()
            ready.set()

        with patch.object(app.overlay, "show_recording", side_effect=shown):
            app.on_hotkey_press()
            assert ready.wait(2), "Microphone did not become ready"

    yield start
    for app in apps:
        app.stop()
