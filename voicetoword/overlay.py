import ctypes
import logging
import queue
import threading
from ctypes import wintypes
from enum import Enum
from typing import Any, Optional, Tuple, Union

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


def _setup_user32() -> None:
    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if user32 is None:
        return
    if hasattr(user32, "GetParent"):
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
    if hasattr(user32, "ShowWindow"):
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL

    if hasattr(user32, "GetWindowLongPtrW"):
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    elif hasattr(user32, "GetWindowLongW"):
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long


try:
    _setup_user32()
except Exception as e:
    logging.getLogger(__name__).warning("Win32 overlay setup failed (%s)", type(e).__name__)


def _get_window_long_ptr(hwnd: int, index: int) -> int:
    user32 = ctypes.windll.user32
    if hasattr(user32, "GetWindowLongPtrW"):
        return user32.GetWindowLongPtrW(hwnd, index)
    return user32.GetWindowLongW(hwnd, index)


def _set_window_long_ptr(hwnd: int, index: int, value: int) -> int:
    user32 = ctypes.windll.user32
    if hasattr(user32, "SetWindowLongPtrW"):
        return user32.SetWindowLongPtrW(hwnd, index, value)
    return user32.SetWindowLongW(hwnd, index, value)


class OverlayIndicator:
    """Floating non-focus-stealing pill badge indicator at the bottom-center of the screen."""

    def __init__(self, headless: bool = False):
        self.headless = headless or (tk is None)
        self.state = OverlayState.HIDDEN
        self.last_error: str = ""
        self._error_version = 0
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._root = None
        self._label = None
        self._result_window = None
        self._is_running = False

        if not self.headless:
            self._start_gui_thread()

    def _start_gui_thread(self) -> None:
        self._is_running = True
        self._thread = threading.Thread(target=self._gui_loop, daemon=True)
        self._thread.start()

    def _gui_loop(self) -> None:
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

        self._check_queue()
        try:
            self._root.mainloop()
        finally:
            # Release Tk objects on the thread that owns their Tcl interpreter.
            self._label = None
            self._result_window = None
            self._root = None
            self._is_running = False

    def _check_queue(self) -> None:
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
                elif action == "RESULT":
                    self._render_result(payload)
                elif action == "CLEAR_RESULT":
                    self._render_clear_result()
                elif action == "STOP":
                    self._root.destroy()
                    return
        except queue.Empty:
            pass

        if self._root:
            self._root.after(30, self._check_queue)

    def _show_no_activate(self) -> None:
        if not self._root:
            return
        try:
            _setup_user32()
            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
            if not hwnd:
                hwnd = self._root.winfo_id()
            # Tk can recreate its wrapper HWND; apply styles immediately before showing it.
            style = _get_window_long_ptr(hwnd, GWL_EXSTYLE)
            _set_window_long_ptr(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
            ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        except Exception:
            self._root.deiconify()

    def _render_recording(self) -> None:
        if self._label and self._root:
            self._label.configure(
                text="  🔴 Đang nghe (Nhả Ctrl để gửi)...",
                fg="#f38ba8"
            )
            self._show_no_activate()

    def _render_processing(self) -> None:
        if self._label and self._root:
            self._label.configure(
                text="  ⏳ Đang nhận diện Groq AI...",
                fg="#fab387"
            )
            self._show_no_activate()

    def _render_error(self, payload: Union[str, Tuple[str, int]]) -> None:
        if isinstance(payload, tuple):
            message, version = payload
        else:
            message, version = payload, self._error_version
        if self._label and self._root:
            self._label.configure(
                text=f"  ❌ {message}",
                fg="#f38ba8"
            )
            self._show_no_activate()
            # Auto hide error after 1.5s
            self._root.after(1500, lambda: self._hide_if_error(version))

    def _hide_if_error(self, version: int) -> None:
        if self.state == OverlayState.ERROR and version == self._error_version:
            self.hide()
            self._render_hide()

    def _render_hide(self) -> None:
        if self._root:
            self._root.withdraw()

    def _render_clear_result(self) -> None:
        if self._result_window is not None and self._result_window.winfo_exists():
            self._result_window.destroy()
        self._result_window = None

    def _render_result(self, text: str) -> None:
        self._render_clear_result()
        window = tk.Toplevel(self._root)
        self._result_window = window
        window.title("VoiceToWord — Kết quả chưa nhập")
        window.geometry("600x260")
        tk.Label(window, text="Chọn văn bản và nhấn Ctrl+C để sao chép thủ công.").pack(padx=12, pady=8)
        box = tk.Text(window, wrap="word", font=("Segoe UI", 11), padx=8, pady=8)
        box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        box.insert("1.0", text)
        box.configure(state="disabled")

        def select_all(event: Any) -> str:
            box.tag_add("sel", "1.0", "end-1c")
            return "break"

        box.bind("<<SelectAll>>", select_all)
        box.focus_set()

    # Public API (Thread-safe)
    def show_recording(self) -> None:
        self.state = OverlayState.RECORDING
        if not self.headless:
            self._queue.put(("RECORDING", None))

    def show_processing(self) -> None:
        self.state = OverlayState.PROCESSING
        if not self.headless:
            self._queue.put(("PROCESSING", None))

    def show_error(self, message: str) -> None:
        self._error_version += 1
        self.state = OverlayState.ERROR
        self.last_error = message
        if not self.headless:
            self._queue.put(("ERROR", (message, self._error_version)))

    def hide(self) -> None:
        self.state = OverlayState.HIDDEN
        if not self.headless:
            self._queue.put(("HIDE", None))

    def show_result(self, text: str) -> None:
        if not self.headless:
            self._queue.put(("RESULT", text))

    def clear_result(self) -> None:
        if not self.headless:
            self._queue.put(("CLEAR_RESULT", None))

    def stop(self) -> None:
        self.hide()
        if not self.headless:
            self._queue.put(("STOP", None))
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
