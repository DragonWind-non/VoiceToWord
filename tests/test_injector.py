from unittest.mock import MagicMock
import pytest
from src.injector import TextInjector


def test_injector_skips_empty_text():
    mock_keyboard = MagicMock()
    mock_clipboard = MagicMock()

    injector = TextInjector(keyboard_controller=mock_keyboard, clipboard=mock_clipboard)
    injector.paste_text("")
    injector.paste_text("   ")

    mock_clipboard.paste.assert_not_called()
    mock_clipboard.copy.assert_not_called()
    mock_keyboard.press.assert_not_called()


def test_injector_preserves_and_restores_clipboard():
    mock_keyboard = MagicMock()
    mock_clipboard = MagicMock()

    mock_clipboard.paste.return_value = "old clipboard content"

    injector = TextInjector(
        keyboard_controller=mock_keyboard,
        clipboard=mock_clipboard,
        restore_delay=0.01
    )

    injector.paste_text("new transcribed text")

    # Verify new text was copied to clipboard
    mock_clipboard.copy.assert_any_call("new transcribed text")

    # Verify Ctrl+V was simulated
    assert mock_keyboard.press.call_count >= 2
    assert mock_keyboard.release.call_count >= 2

    # Verify old content was restored
    mock_clipboard.copy.assert_called_with("old clipboard content")
