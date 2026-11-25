"""
Lightweight process-hygiene helpers:

- hide the console window (so a compiled onefile with console subsystem
  still looks like a GUI service)
- set the GUI window title to something generic
- avoid writing identifiable strings to the taskbar
"""
import ctypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

SW_HIDE = 0

def hide_console():
    try:
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, SW_HIDE)
    except Exception:
        pass

def set_window_title(title: str):
    """Set the console window + current process title where possible."""
    try:
        kernel32.SetConsoleTitleW(title)
    except Exception:
        pass
