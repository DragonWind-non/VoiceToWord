import logging
from typing import Callable, Optional
from pynput.keyboard import Key, KeyCode, Listener


log = logging.getLogger(__name__)


KEY_MAP = {
    "ctrl_r": Key.ctrl_r,
    "ctrl_l": Key.ctrl_l,
    "alt_r": getattr(Key, "alt_r", Key.alt_gr),
    "alt_l": Key.alt_l,
    "shift_r": Key.shift_r,
    "shift_l": Key.shift_l,
    "caps_lock": Key.caps_lock,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f12": Key.f12,
}


class HotkeyListener:
    """Global keyboard hook listening for push-to-talk key with repeat suppression."""

    def __init__(
        self,
        target_key: str = "ctrl_r",
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
    ):
        self.target_key_name = target_key.lower().strip()
        self.target_key = KEY_MAP.get(self.target_key_name, Key.ctrl_r)
        self.on_press = on_press or (lambda: None)
        self.on_release = on_release or (lambda: None)

        self.is_held = False
        self._listener: Optional[Listener] = None

    def _matches_target(self, key) -> bool:
        """Check if received key event matches target key."""
        if key == self.target_key:
            return True

        # Special handling for Right Alt / AltGr on Windows
        if self.target_key_name == "alt_r" and key in (getattr(Key, "alt_r", None), Key.alt_gr):
            return True

        return False

    def _handle_press(self, key) -> None:
        """Called whenever any key is pressed."""
        if self._matches_target(key):
            if not self.is_held:
                self.is_held = True
                try:
                    self.on_press()
                except Exception as e:
                    log.error("Hotkey on_press callback error: %s", e)

    def _handle_release(self, key) -> None:
        """Called whenever any key is released."""
        if self._matches_target(key):
            if self.is_held:
                self.is_held = False
                try:
                    self.on_release()
                except Exception as e:
                    log.error("Hotkey on_release callback error: %s", e)

    def start(self) -> None:
        """Start listening for keyboard events in a background thread."""
        if self._listener is None:
            self._listener = Listener(
                on_press=self._handle_press,
                on_release=self._handle_release,
            )
            self._listener.daemon = True
            self._listener.start()

    def stop(self) -> None:
        """Stop listening for keyboard events."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            finally:
                self._listener = None
            self.is_held = False
