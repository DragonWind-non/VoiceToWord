import logging
import threading
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw


def create_tray_icon_image() -> Image.Image:
    """Generate a clean 64x64 microphone icon image for the system tray."""
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Outer circle background
    draw.ellipse([4, 4, 60, 60], fill=(30, 30, 46, 255), outline=(137, 180, 250, 255), width=2)

    # Microphone capsule
    draw.rounded_rectangle([26, 16, 38, 36], radius=6, fill=(137, 180, 250, 255))

    # Microphone arc / stand
    draw.arc([20, 24, 44, 44], start=0, end=180, fill=(205, 214, 244, 255), width=2)
    draw.line([32, 44, 32, 52], fill=(205, 214, 244, 255), width=2)
    draw.line([24, 52, 40, 52], fill=(205, 214, 244, 255), width=2)

    return image


class TrayManager:
    """Manages the Windows notification area (System Tray) icon and context menu."""

    def __init__(self, on_exit: Optional[Callable[[], None]] = None,
                 on_show_result: Optional[Callable[[], None]] = None):
        self.on_exit = on_exit or (lambda: None)
        self.on_show_result = on_show_result or (lambda: None)
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _create_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("VoiceToWord (Giữ Right Ctrl để nói)", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Xem kết quả chưa nhập", lambda icon, item: self.on_show_result()),
            pystray.MenuItem("Thoát (Exit)", self._handle_exit),
        )

    def _handle_exit(self, icon, item):
        self.stop()
        self.on_exit()

    def start(self) -> None:
        """Start the system tray icon in a dedicated daemon thread."""
        image = create_tray_icon_image()
        self._icon = pystray.Icon(
            name="VoiceToWord",
            icon=image,
            title="VoiceToWord - Giữ Right Ctrl để nói",
            menu=self._create_menu(),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Remove the system tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to stop tray icon (%s)", type(e).__name__)
            finally:
                self._icon = None
