import re
from typing import Optional
from pynput.keyboard import Controller


class TextInjector:
    def __init__(self, keyboard_controller: Optional[Controller] = None):
        self.keyboard = keyboard_controller if keyboard_controller is not None else Controller()

    def paste_text(self, text: str) -> bool:
        """Type Unicode text without touching the user's clipboard."""
        if not text or not text.strip():
            return False

        try:
            # shortcut: flatten control whitespace, revisit when multiline insertion is safe without Enter.
            self.keyboard.type(re.sub(r"[\r\n\t]+", " ", text))
            return True
        except Exception:
            return False
