"""
ALX2.0 — Python entry.

Enable debug logging in one of two ways:
  1) Set ALX_DEBUG=1 in your environment, or
  2) Add  "debug": true  inside the "main" block of config.json.
Output goes to BOTH stdout (when a console exists) AND to alx_debug.log
next to the exe/script — so even the --windowed compiled build logs.
"""
import os
import sys
import json
from pathlib import Path

# PRE-IMPORT CHECK: look at config.json for a debug flag before importing
# other modules, so their module-level DEBUG constants pick it up too.
try:
    _frozen = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
    _base = Path(sys.executable).resolve().parent if _frozen else Path(__file__).resolve().parent
    _cfg_path = _base / "config.json"
    if _cfg_path.exists():
        with open(_cfg_path, "r", encoding="utf-8") as _f:
            _c = json.load(_f)
        if _c.get("main", {}).get("debug") is True:
            os.environ["ALX_DEBUG"] = "1"
except Exception:
    pass

from config import Config
from humanizer import Humanizer
import input_backend
from engine import Engine
from hotkeys import HotkeyRouter
from raw_input import RawInputListener
from keyboard_hook import KeyboardHook
from custom_macros import CustomMacroRunner
import stealth


def _ensure_pyside6():
    """If PySide6 isn't importable in THIS Python interpreter, pip-install
    it into this same interpreter. Covers the common pitfall where a user
    ran `pip install PySide6` under a different Python than the one that
    starts main.py (pyenv, store Python, venv, portable install, etc.)."""
    try:
        import PySide6  # noqa: F401
        return
    except ImportError:
        pass
    import subprocess
    # frozen (PyInstaller) builds already bundle PySide6 — nothing to do here
    if getattr(sys, "frozen", False):
        _die("PySide6 is missing from the compiled build.\n"
             "Rebuild with build.py — it now pulls PySide6 in automatically.")
    print("[alx] PySide6 not found — installing it into this Python...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "PySide6"]
    )
    if r.returncode != 0:
        _die("Could not install PySide6 automatically.\n\n"
             "Open a terminal and run:\n"
             f'    "{sys.executable}" -m pip install PySide6\n\n'
             "then run ALX again.")
    try:
        import PySide6  # noqa: F401
    except ImportError as e:
        _die(f"PySide6 installed but still not importable: {e}\n"
             f"Interpreter: {sys.executable}")


def _die(msg: str):
    """Show the error in a popup if we can, otherwise print it."""
    print("[alx] FATAL:", msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "ALX2.0", 0x10)
    except Exception:
        try:
            import tkinter as _tk
            from tkinter import messagebox
            r = _tk.Tk(); r.withdraw()
            messagebox.showerror("ALX2.0", msg)
            r.destroy()
        except Exception:
            pass
    sys.exit(1)


_ensure_pyside6()

# Qt must have a QApplication before any widget is created.
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
# Enable HiDPI pixmaps etc. (Qt6: HiDPI is automatic; only pixmaps opt-in)
try:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
except Exception:
    pass

from gui import App


class _Tee:
    """Write to multiple file-like objects at once."""
    def __init__(self, *files):
        self.files = tuple(f for f in files if f is not None)
    def write(self, s):
        for f in self.files:
            try: f.write(s); f.flush()
            except Exception: pass
    def flush(self):
        for f in self.files:
            try: f.flush()
            except Exception: pass


def _install_debug_tee():
    """When ALX_DEBUG=1, mirror stdout/stderr to alx_debug.log next to the
    running exe/script. Works for both python main.py and the compiled exe
    (which has no console at all)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    log_path = base / "alx_debug.log"
    try:
        log_file = open(log_path, "w", encoding="utf-8", buffering=1)
    except Exception:
        return
    # In --windowed PyInstaller builds, sys.stdout / sys.stderr are None.
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)
    print(f"[alx] debug log: {log_path}")


def main():
    cfg = Config()

    debug = os.environ.get("ALX_DEBUG") == "1"
    if debug:
        _install_debug_tee()

    s = cfg.stealth()
    # keep console visible in debug mode so prints are seen
    if s.get("hide_console") and not debug:
        stealth.hide_console()
    title = s.get("window_title", "System Audio Service")
    stealth.set_window_title(title)

    hu = Humanizer(cfg)
    bk = input_backend.make_backend(cfg.backend_name())
    print(f"[alx] backend: {bk.name}")

    engine = Engine(cfg, bk, hu)

    exit_flag = {"done": False}
    def on_toggle():
        engine.toggle()
        try: app._refresh_status()
        except Exception: pass
    def on_exit():
        if exit_flag["done"]: return
        exit_flag["done"] = True
        try: engine.shutdown()
        except Exception: pass
        try: macros.cancel_all()
        except Exception: pass
        try: kbhook.stop()
        except Exception: pass
        try: listener.stop()
        except Exception: pass
        try:
            from PySide6.QtWidgets import QApplication as _QA
            _QA.quit()
        except Exception: pass

    listener = RawInputListener()
    macros = CustomMacroRunner(cfg, bk)
    router = HotkeyRouter(engine, cfg, on_toggle=on_toggle, on_exit=on_exit,
                          listener=listener, custom_macros=macros)
    listener.set_on_key(router.on_key_event)
    listener.set_on_mouse(router.on_mouse_event)
    listener.start()
    router.rebuild()

    kbhook = KeyboardHook(engine, cfg, bk)
    kbhook.start()

    # Qt app must live for the entire session
    qapp = QApplication.instance() or QApplication(sys.argv)
    qapp.setStyle("Fusion")

    app = App(cfg, engine, router, on_exit=on_exit, window_title=title,
              listener=listener, custom_macros=macros)
    try:
        app.run()
    finally:
        on_exit()
        sys.exit(0)


if __name__ == "__main__":
    main()
