import time
from typing import Optional
import pyperclip
from pynput.keyboard import Controller, Key


class TextInjector:
    def __init__(
        self,
        keyboard_controller: Optional[Controller] = None,
        clipboard=None,
        restore_delay: float = 0.08,
    ):
        self.keyboard = keyboard_controller if keyboard_controller is not None else Controller()
        self.clipboard = clipboard if clipboard is not None else pyperclip
        self.restore_delay = restore_delay

    def paste_text(self, text: str) -> bool:
        """Paste text into active foreground window while preserving prior clipboard content."""
        if not text or not text.strip():
            return False

        old_clipboard: Optional[str] = None
        try:
            old_clipboard = self.clipboard.paste()
        except Exception:
            old_clipboard = None

        try:
            # Copy text to clipboard
            self.clipboard.copy(text)
            time.sleep(0.01)

            # Trigger Ctrl+V keystroke
            self.keyboard.press(Key.ctrl)
            self.keyboard.press('v')
            self.keyboard.release('v')
            self.keyboard.release(Key.ctrl)

            # Wait briefly for target application to read the clipboard
            time.sleep(self.restore_delay)

            # Restore original clipboard
            if old_clipboard is not None:
                self.clipboard.copy(old_clipboard)

            return True
        except Exception as e:
            # Attempt to restore clipboard on error
            if old_clipboard is not None:
                try:
                    self.clipboard.copy(old_clipboard)
                except Exception:
                    pass
            print(f"[TextInjector] Error pasting text: {e}")
            return False
