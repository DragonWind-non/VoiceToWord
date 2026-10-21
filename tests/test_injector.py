from unittest.mock import MagicMock
import pytest
from src.injector import TextInjector


def test_injector_skips_empty_text():
    mock_keyboard = MagicMock()
    mock_clipboard = MagicMock()

    injector = TextInjector(keyboard_controller=mock_keyboard)
    injector.paste_text("")
    injector.paste_text("   ")

    mock_clipboard.paste.assert_not_called()
    mock_clipboard.copy.assert_not_called()
    mock_keyboard.press.assert_not_called()


def test_injector_keeps_nontext_clipboard_untouched():
    keyboard = MagicMock()
    clipboard = MagicMock()
    injector = TextInjector(keyboard_controller=keyboard)

    assert injector.paste_text("Tiếng Việt") is True
    keyboard.type.assert_called_once_with("Tiếng Việt")
    clipboard.paste.assert_not_called()
    clipboard.copy.assert_not_called()


def test_injector_does_not_send_transcript_line_breaks_as_enter():
    keyboard = MagicMock()
    injector = TextInjector(keyboard_controller=keyboard)

    assert injector.paste_text("git status\nrm -rf /\tmore") is True
    keyboard.type.assert_called_once_with("git status rm -rf / more")


def test_injector_reports_typing_failure():
    keyboard = MagicMock()
    keyboard.type.side_effect = RuntimeError("input blocked")
    assert TextInjector(keyboard_controller=keyboard).paste_text("text") is False
