from unittest.mock import MagicMock

from pynput.keyboard import Key, KeyCode

from voicetoword.hotkey_listener import HotkeyListener


def test_hotkey_listener_press_and_release():
    mock_press = MagicMock()
    mock_release = MagicMock()

    listener = HotkeyListener(target_key="ctrl_r", on_press=mock_press, on_release=mock_release)

    # First press of Right Ctrl
    listener._handle_press(Key.ctrl_r)
    assert mock_press.call_count == 1
    assert listener.is_held is True

    # Repeated press while held (OS key repeat simulation)
    listener._handle_press(Key.ctrl_r)
    listener._handle_press(Key.ctrl_r)
    assert mock_press.call_count == 1  # Should still be 1!

    # Release of Right Ctrl
    listener._handle_release(Key.ctrl_r)
    assert mock_release.call_count == 1
    assert listener.is_held is False


def test_hotkey_listener_ignores_other_keys():
    mock_press = MagicMock()
    mock_release = MagicMock()

    listener = HotkeyListener(target_key="ctrl_r", on_press=mock_press, on_release=mock_release)

    # Press Left Ctrl (should be ignored)
    listener._handle_press(Key.ctrl_l)
    assert mock_press.call_count == 0
    assert listener.is_held is False

    # Press regular key 'c'
    listener._handle_press(KeyCode.from_char('c'))
    assert mock_press.call_count == 0

    # Release Left Ctrl
    listener._handle_release(Key.ctrl_l)
    assert mock_release.call_count == 0
