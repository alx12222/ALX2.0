"""
Three output backends behind one interface.

- SendInputBackend / MouseEventBackend : user-mode. Events carry LLMHF_INJECTED.
- InterceptionBackend                  : kernel driver. Events do NOT carry the
                                         injected flag. Driver must be installed
                                         separately (interception.dll + the
                                         install-interception.exe install step).

Factory: make_backend(name) → auto-prefers interception if available.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
from pathlib import Path

# ======================= Win32 shared =======================
ULONG_PTR = ctypes.c_size_t

# Magic value we stamp into dwExtraInfo on every output event we send.
# The RawInputListener filters any event carrying this tag so our own
# synthesized events don't echo back as "physical" input.
ALX_EXTRA_INFO = 0xA7CBA070

try:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
except OSError:
    user32 = None

# ======================= SendInput backend =======================
INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP    = 0x0002
KEYEVENTF_EXTENDED = 0x0001

MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_XDOWN      = 0x0080
MOUSEEVENTF_XUP        = 0x0100
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ULONG_PTR)]

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG),
                ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]

class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUT_UNION)]

if user32:
    _SendInput = user32.SendInput
    _SendInput.argtypes = (wt.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    _SendInput.restype = wt.UINT
    _mouse_event = user32.mouse_event
    _mouse_event.argtypes = (wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, ULONG_PTR)
    _mouse_event.restype = None
else:
    _SendInput = None
    _mouse_event = None

SCAN = {
    "esc": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "-": 0x0C, "=": 0x0D, "backspace": 0x0E, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14, "y": 0x15,
    "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "[": 0x1A, "]": 0x1B, "enter": 0x1C, "lctrl": 0x1D, "ctrl": 0x1D,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22, "h": 0x23,
    "j": 0x24, "k": 0x25, "l": 0x26, ";": 0x27, "'": 0x28, "`": 0x29,
    "lshift": 0x2A, "shift": 0x2A, "\\": 0x2B,
    "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30, "n": 0x31,
    "m": 0x32, ",": 0x33, ".": 0x34, "/": 0x35, "rshift": 0x36,
    "lalt": 0x38, "alt": 0x38, "space": 0x39, "capslock": 0x3A,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F,
    "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44,
    "f11": 0x57, "f12": 0x58,
    "home": 0x47, "up": 0x48, "pageup": 0x49, "left": 0x4B, "right": 0x4D,
    "end": 0x4F, "down": 0x50, "pagedown": 0x51, "insert": 0x52, "delete": 0x53,
}
EXTENDED = {0x47, 0x48, 0x49, 0x4B, 0x4D, 0x4F, 0x50, 0x51, 0x52, 0x53}

def _is_mouse(name: str) -> bool:
    n = name.lower()
    return n in ("lbutton", "rbutton", "mbutton",
                 "xbutton1", "xbutton2", "mb4", "mb5",
                 "mouse_left", "mouse_right", "mouse_middle",
                 "mouse_x1", "mouse_x2", "left", "right", "middle")

def _mouse_flags(name: str):
    n = name.lower()
    if n in ("lbutton", "mouse_left", "left"):
        return MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 0, "left"
    if n in ("rbutton", "mouse_right", "right"):
        return MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, 0, "right"
    if n in ("mbutton", "mouse_middle", "middle"):
        return MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP, 0, "middle"
    if n in ("xbutton1", "mb4", "mouse_x1"):
        return MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, XBUTTON1, "x1"
    if n in ("xbutton2", "mb5", "mouse_x2"):
        return MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, XBUTTON2, "x2"
    return 0, 0, 0, ""


class SendInputBackend:
    name = "sendinput"

    def mouse_down(self, name):
        if not _mouse_event: return
        down, _, data, _ = _mouse_flags(name)
        if down: _mouse_event(down, 0, 0, data, ALX_EXTRA_INFO)

    def mouse_up(self, name):
        if not _mouse_event: return
        _, up, data, _ = _mouse_flags(name)
        if up: _mouse_event(up, 0, 0, data, ALX_EXTRA_INFO)

    def key_down(self, name):
        if _is_mouse(name):
            return self.mouse_down(name)
        s = SCAN.get(name.lower())
        if s is not None and _SendInput:
            self._key(s, False)

    def key_up(self, name):
        if _is_mouse(name):
            return self.mouse_up(name)
        s = SCAN.get(name.lower())
        if s is not None and _SendInput:
            self._key(s, True)

    def send(self, name, hold_ms=30):
        if _is_mouse(name):
            self.mouse_down(name)
            time.sleep(hold_ms / 1000.0)
            self.mouse_up(name)
            return
        s = SCAN.get(name.lower())
        if s is None or not _SendInput: return
        self._key(s, False); time.sleep(hold_ms / 1000.0); self._key(s, True)

    def _key(self, scan, up):
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
        if scan in EXTENDED: flags |= KEYEVENTF_EXTENDED
        inp = _INPUT(type=INPUT_KEYBOARD)
        inp.ki = _KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0,
                             dwExtraInfo=ALX_EXTRA_INFO)
        _SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


# ======================= Interception backend =======================
INTERCEPTION_KEY_DOWN = 0x00
INTERCEPTION_KEY_UP   = 0x01
INTERCEPTION_KEY_E0   = 0x02

I_M_LEFT_DOWN   = 0x001
I_M_LEFT_UP     = 0x002
I_M_RIGHT_DOWN  = 0x004
I_M_RIGHT_UP    = 0x008
I_M_MIDDLE_DOWN = 0x010
I_M_MIDDLE_UP   = 0x020
I_M_B4_DOWN     = 0x040
I_M_B4_UP       = 0x080
I_M_B5_DOWN     = 0x100
I_M_B5_UP       = 0x200

class _IKeyStroke(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort),
                ("state", ctypes.c_ushort),
                ("information", ctypes.c_uint)]

class _IMouseStroke(ctypes.Structure):
    _fields_ = [("state", ctypes.c_ushort),
                ("flags", ctypes.c_ushort),
                ("rolling", ctypes.c_short),
                ("x", ctypes.c_int),
                ("y", ctypes.c_int),
                ("information", ctypes.c_uint)]

def _load_interception_dll():
    # try: next to script/exe, cwd, system paths
    candidates = []
    base = Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else Path.cwd()
    candidates.append(base / "interception.dll")
    candidates.append(Path.cwd() / "interception.dll")
    # try plain load (uses DLL search path)
    try:
        return ctypes.WinDLL("interception.dll")
    except OSError:
        pass
    for p in candidates:
        if p.exists():
            try:
                return ctypes.WinDLL(str(p))
            except OSError:
                continue
    return None


class InterceptionBackend:
    name = "interception"

    def __init__(self):
        self.dll = _load_interception_dll()
        if not self.dll:
            raise RuntimeError("interception.dll not found")

        self.dll.interception_create_context.restype  = ctypes.c_void_p
        self.dll.interception_destroy_context.argtypes = [ctypes.c_void_p]
        self.dll.interception_send.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        self.dll.interception_send.restype = ctypes.c_int
        self.dll.interception_is_keyboard.argtypes = [ctypes.c_int]
        self.dll.interception_is_mouse.argtypes = [ctypes.c_int]

        self.ctx = self.dll.interception_create_context()
        if not self.ctx:
            raise RuntimeError("interception_create_context failed — driver not installed?")

        # pick first available keyboard (1-10) and mouse (11-20)
        self.kbd_dev = None
        self.mouse_dev = None
        for d in range(1, 11):
            if self.dll.interception_is_keyboard(d):
                self.kbd_dev = d; break
        for d in range(11, 21):
            if self.dll.interception_is_mouse(d):
                self.mouse_dev = d; break
        if self.kbd_dev is None: self.kbd_dev = 1
        if self.mouse_dev is None: self.mouse_dev = 11

    def __del__(self):
        try:
            if getattr(self, "ctx", None) and self.dll:
                self.dll.interception_destroy_context(self.ctx)
        except Exception:
            pass

    def _mouse_state_for(self, name, down):
        n = name.lower()
        if n in ("lbutton", "mouse_left", "left"):
            return I_M_LEFT_DOWN if down else I_M_LEFT_UP
        if n in ("rbutton", "mouse_right", "right"):
            return I_M_RIGHT_DOWN if down else I_M_RIGHT_UP
        if n in ("mbutton", "mouse_middle", "middle"):
            return I_M_MIDDLE_DOWN if down else I_M_MIDDLE_UP
        if n in ("xbutton1", "mb4", "mouse_x1"):
            return I_M_B4_DOWN if down else I_M_B4_UP
        if n in ("xbutton2", "mb5", "mouse_x2"):
            return I_M_B5_DOWN if down else I_M_B5_UP
        return 0

    def _send_mouse(self, state):
        stroke = _IMouseStroke(state=state, flags=0, rolling=0, x=0, y=0,
                               information=ALX_EXTRA_INFO)
        self.dll.interception_send(self.ctx, self.mouse_dev,
                                   ctypes.byref(stroke), 1)

    def _send_key(self, scan, up):
        state = INTERCEPTION_KEY_UP if up else INTERCEPTION_KEY_DOWN
        if scan in EXTENDED:
            state |= INTERCEPTION_KEY_E0
        stroke = _IKeyStroke(code=scan, state=state, information=ALX_EXTRA_INFO)
        self.dll.interception_send(self.ctx, self.kbd_dev,
                                   ctypes.byref(stroke), 1)

    def mouse_down(self, name):
        s = self._mouse_state_for(name, down=True)
        if s: self._send_mouse(s)

    def mouse_up(self, name):
        s = self._mouse_state_for(name, down=False)
        if s: self._send_mouse(s)

    def key_down(self, name):
        if _is_mouse(name):
            return self.mouse_down(name)
        scan = SCAN.get(name.lower())
        if scan is not None:
            self._send_key(scan, up=False)

    def key_up(self, name):
        if _is_mouse(name):
            return self.mouse_up(name)
        scan = SCAN.get(name.lower())
        if scan is not None:
            self._send_key(scan, up=True)

    def send(self, name, hold_ms=30):
        if _is_mouse(name):
            self.mouse_down(name)
            time.sleep(hold_ms / 1000.0)
            self.mouse_up(name)
            return
        scan = SCAN.get(name.lower())
        if scan is None: return
        self._send_key(scan, up=False)
        time.sleep(hold_ms / 1000.0)
        self._send_key(scan, up=True)


# ======================= factory =======================
def make_backend(name: str = "auto"):
    name = (name or "auto").lower()
    if name in ("auto",):
        try:
            return InterceptionBackend()
        except Exception as e:
            print(f"[backend] interception unavailable ({e}); using sendinput")
            return SendInputBackend()
    if name == "interception":
        return InterceptionBackend()
    return SendInputBackend()
