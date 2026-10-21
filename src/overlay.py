import ctypes
from enum import Enum
import queue
import threading
import time
from typing import Optional

try:
    import tkinter as tk
except ImportError:
    tk = None


class OverlayState(Enum):
    HIDDEN = "hidden"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


# Windows Extended Window Styles
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
SW_SHOWNOACTIVATE = 4
SW_HIDE = 0


class OverlayIndicator:
    """Floating non-focus-stealing pill badge indicator at the bottom-center of the screen."""

    def __init__(self, headless: bool = False):
        self.headless = headless or (tk is None)
        self.state = OverlayState.HIDDEN
        self.last_error: str = ""
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._root = None
        self._label = None
        self._is_running = False

        if not self.headless:
            self._start_gui_thread()

    def _start_gui_thread(self):
        self._is_running = True
        self._thread = threading.Thread(target=self._gui_loop, daemon=True)
        self._thread.start()

    def _gui_loop(self):
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.configure(bg="#181825")

        # Create styled pill container
        container = tk.Frame(self._root, bg="#1e1e2e", padx=16, pady=8, highlightbackground="#45475a", highlightthickness=1)
        container.pack(fill="both", expand=True)

        self._label = tk.Label(
            container,
            text="",
            font=("Segoe UI", 10, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
        )
        self._label.pack()

        # Center horizontally at the bottom of the screen (60px above taskbar)
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        width = 280
        height = 42
        x = (screen_w - width) // 2
        y = screen_h - 110
        self._root.geometry(f"{width}x{height}+{x}+{y}")

        # Set Windows WS_EX_NOACTIVATE style on the HWND to ensure it NEVER steals focus
        try:
            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
            if not hwnd:
                hwnd = self._root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= (WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

        self._check_queue()
        self._root.mainloop()

    def _check_queue(self):
        if not self._root:
            return

        try:
            while True:
                action, payload = self._queue.get_nowait()
                if action == "RECORDING":
                    self._render_recording()
                elif action == "PROCESSING":
                    self._render_processing()
                elif action == "ERROR":
                    self._render_error(payload)
                elif action == "HIDE":
                    self._render_hide()
                elif action == "STOP":
                    self._root.destroy()
                    return
        except queue.Empty:
            pass

        if self._root:
            self._root.after(30, self._check_queue)

    def _show_no_activate(self):
        if not self._root:
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
            if not hwnd:
                hwnd = self._root.winfo_id()
            ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        except Exception:
            self._root.deiconify()

    def _render_recording(self):
        if self._label and self._root:
            self._label.configure(
                text="  🔴 Đang nghe (Nhả Ctrl để gửi)...",
                fg="#f38ba8"
            )
            self._show_no_activate()

    def _render_processing(self):
        if self._label and self._root:
            self._label.configure(
                text="  ⏳ Đang nhận diện Groq AI...",
                fg="#fab387"
            )
            self._show_no_activate()

    def _render_error(self, message: str):
        if self._label and self._root:
            self._label.configure(
                text=f"  ❌ {message}",
                fg="#f38ba8"
            )
            self._show_no_activate()
            # Auto hide error after 1.5s
            self._root.after(1500, self._render_hide)

    def _render_hide(self):
        if self._root:
            self._root.withdraw()

    # Public API (Thread-safe)
    def show_recording(self):
        self.state = OverlayState.RECORDING
        if not self.headless:
            self._queue.put(("RECORDING", None))

    def show_processing(self):
        self.state = OverlayState.PROCESSING
        if not self.headless:
            self._queue.put(("PROCESSING", None))

    def show_error(self, message: str):
        self.state = OverlayState.ERROR
        self.last_error = message
        if not self.headless:
            self._queue.put(("ERROR", message))

    def hide(self):
        self.state = OverlayState.HIDDEN
        if not self.headless:
            self._queue.put(("HIDE", None))

    def stop(self):
        self.hide()
        if not self.headless:
            self._queue.put(("STOP", None))
