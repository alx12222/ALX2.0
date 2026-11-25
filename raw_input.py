"""
GetRawInputData-based global input listener.

64-bit-safe ctypes signatures. Replaces the keyboard/mouse pip libraries,
which install WH_KEYBOARD_LL / WH_MOUSE_LL hooks visible to anti-cheat.
Raw Input runs via a hidden message window with no installed hook.

Set ALX_DEBUG=1 in the environment to print every received event.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DEBUG = os.environ.get("ALX_DEBUG") == "1"

# ---------------- types ----------------
LRESULT   = ctypes.c_ssize_t
LONG_PTR  = ctypes.c_ssize_t
LPVOID    = ctypes.c_void_p
HWND      = wt.HWND
HANDLE    = wt.HANDLE
HINSTANCE = wt.HINSTANCE
HICON     = wt.HICON
HBRUSH    = wt.HBRUSH
HCURSOR   = wt.HANDLE
LPCWSTR   = wt.LPCWSTR
BOOL      = wt.BOOL
UINT      = wt.UINT
WPARAM    = wt.WPARAM
LPARAM    = wt.LPARAM
DWORD     = wt.DWORD
ATOM      = ctypes.c_ushort
USHORT    = ctypes.c_ushort
SHORT     = ctypes.c_short
ULONG     = wt.ULONG

HWND_MESSAGE = HWND(-3)

# ---------------- constants ----------------
WM_INPUT   = 0x00FF
WM_QUIT    = 0x0012
WM_DESTROY = 0x0002
WM_CLOSE   = 0x0010

RIDEV_INPUTSINK  = 0x00000100
RIDEV_REMOVE     = 0x00000001
RID_INPUT        = 0x10000003
RIM_TYPEMOUSE    = 0
RIM_TYPEKEYBOARD = 1

# Thread priority constants
THREAD_PRIORITY_ABOVE_NORMAL = 1
THREAD_PRIORITY_HIGHEST      = 2

RI_MOUSE_LEFT_BUTTON_DOWN   = 0x0001
RI_MOUSE_LEFT_BUTTON_UP     = 0x0002
RI_MOUSE_RIGHT_BUTTON_DOWN  = 0x0004
RI_MOUSE_RIGHT_BUTTON_UP    = 0x0008
RI_MOUSE_MIDDLE_BUTTON_DOWN = 0x0010
RI_MOUSE_MIDDLE_BUTTON_UP   = 0x0020
RI_MOUSE_BUTTON_4_DOWN      = 0x0040
RI_MOUSE_BUTTON_4_UP        = 0x0080
RI_MOUSE_BUTTON_5_DOWN      = 0x0100
RI_MOUSE_BUTTON_5_UP        = 0x0200

RI_KEY_MAKE  = 0x00
RI_KEY_BREAK = 0x01
RI_KEY_E0    = 0x02
RI_KEY_E1    = 0x04

# Must match input_backend.ALX_EXTRA_INFO
ALX_EXTRA_INFO = 0xA7CBA070

# ---------------- structs ----------------
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", LPCWSTR),
        ("lpszClassName", LPCWSTR),
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("message", UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", DWORD),
        ("pt", POINT),
    ]

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", USHORT),
        ("usUsage", USHORT),
        ("dwFlags", DWORD),
        ("hwndTarget", HWND),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", DWORD),
        ("dwSize", DWORD),
        ("hDevice", HANDLE),
        ("wParam", WPARAM),
    ]

class _RAWMOUSE_BTN(ctypes.Structure):
    _fields_ = [("usButtonFlags", USHORT), ("usButtonData", USHORT)]

class _RAWMOUSE_U(ctypes.Union):
    _fields_ = [("ulButtons", ULONG), ("s", _RAWMOUSE_BTN)]

class RAWMOUSE(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("usFlags", USHORT),
        ("u", _RAWMOUSE_U),
        ("ulRawButtons", ULONG),
        ("lLastX", wt.LONG),
        ("lLastY", wt.LONG),
        ("ulExtraInformation", ULONG),
    ]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", USHORT),
        ("Flags", USHORT),
        ("Reserved", USHORT),
        ("VKey", USHORT),
        ("Message", UINT),
        ("ExtraInformation", ULONG),
    ]

class _RAWINPUT_DATA(ctypes.Union):
    _fields_ = [("mouse", RAWMOUSE), ("keyboard", RAWKEYBOARD)]

class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("data", _RAWINPUT_DATA)]

# ---------------- API signatures (critical on 64-bit) ----------------
user32.DefWindowProcW.argtypes = (HWND, UINT, WPARAM, LPARAM)
user32.DefWindowProcW.restype  = LRESULT

user32.RegisterClassW.argtypes = (ctypes.POINTER(WNDCLASSW),)
user32.RegisterClassW.restype  = ATOM

user32.CreateWindowExW.argtypes = (
    DWORD, LPCWSTR, LPCWSTR, DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    HWND, HANDLE, HINSTANCE, LPVOID,
)
user32.CreateWindowExW.restype = HWND

user32.DestroyWindow.argtypes = (HWND,)
user32.DestroyWindow.restype  = BOOL

user32.GetMessageW.argtypes = (ctypes.POINTER(MSG), HWND, UINT, UINT)
user32.GetMessageW.restype  = ctypes.c_int

user32.TranslateMessage.argtypes = (ctypes.POINTER(MSG),)
user32.TranslateMessage.restype  = BOOL

user32.DispatchMessageW.argtypes = (ctypes.POINTER(MSG),)
user32.DispatchMessageW.restype  = LRESULT

user32.PostMessageW.argtypes = (HWND, UINT, WPARAM, LPARAM)
user32.PostMessageW.restype  = BOOL

user32.PostQuitMessage.argtypes = (ctypes.c_int,)
user32.PostQuitMessage.restype  = None

user32.RegisterRawInputDevices.argtypes = (
    ctypes.POINTER(RAWINPUTDEVICE), UINT, UINT,
)
user32.RegisterRawInputDevices.restype  = BOOL

user32.GetRawInputData.argtypes = (
    HANDLE, UINT, LPVOID, ctypes.POINTER(UINT), UINT,
)
user32.GetRawInputData.restype  = UINT

kernel32.GetModuleHandleW.argtypes = (LPCWSTR,)
kernel32.GetModuleHandleW.restype  = HINSTANCE

kernel32.GetCurrentThread.argtypes = ()
kernel32.GetCurrentThread.restype  = HANDLE
kernel32.SetThreadPriority.argtypes = (HANDLE, ctypes.c_int)
kernel32.SetThreadPriority.restype  = BOOL

# ---------------- VK name map ----------------
VK_NAMES = {}
for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    VK_NAMES[ord(ch)] = ch.lower()
for d in "0123456789":
    VK_NAMES[ord(d)] = d
VK_NAMES.update({
    0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x1B: "esc", 0x20: "space",
    0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
    0x2D: "insert", 0x2E: "delete", 0x24: "home", 0x23: "end",
    0x21: "pageup", 0x22: "pagedown", 0x14: "capslock",
    0x10: "shift", 0x11: "ctrl", 0x12: "alt",
    0xA0: "lshift", 0xA1: "rshift", 0xA2: "lctrl", 0xA3: "rctrl",
    0xA4: "lalt", 0xA5: "ralt",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/",
    0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
})
for i in range(1, 13):
    VK_NAMES[0x6F + i] = f"f{i}"


def vk_to_name(vk: int) -> str:
    return VK_NAMES.get(vk, "")


# ---------------- listener ----------------
class RawInputListener:
    """
    Fires on_key(name, is_down) and on_mouse(button, is_down) on its own
    message-pump thread.

    Performance-critical: the WndProc runs for every keyboard event and
    (when mouse is subscribed) for every mouse motion packet, which can be
    1000+/sec. Keep the hot path minimal.

    Mouse subscription is dynamic — call set_mouse_subscribed(False) when
    the macro doesn't need to see left-click to eliminate most of the
    runtime cost (mouse motion packets dominate the event stream).
    """

    _HEADER_SIZE = ctypes.sizeof(RAWINPUTHEADER)
    _BUF_SIZE    = 256  # one RAWINPUT fits easily

    def __init__(self):
        self._on_key = None
        self._on_mouse = None
        self._thread = None
        self._hwnd = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._wndproc_ref = None
        self._class_atom = 0
        self._first_event_logged = False

        # Reusable scratch buffer for GetRawInputData — allocating a new
        # (ctypes.c_byte * N)() per event is a lot of GC pressure at 1kHz.
        self._buf = (ctypes.c_byte * self._BUF_SIZE)()
        self._ri_ptr = ctypes.cast(self._buf, ctypes.POINTER(RAWINPUT))

        # subscription state (changes with config / GUI capture needs)
        self._want_kbd       = True
        self._cfg_want_mouse = True   # set by set_mouse_subscribed (config)
        self._mouse_refs     = 0      # push/pop'd by GUI capture
        self._sub_lock       = threading.Lock()
        self._applied_mouse  = None   # last state actually sent to Windows

    def set_on_key(self, cb):   self._on_key = cb
    def set_on_mouse(self, cb): self._on_mouse = cb

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=3.0):
            print("[raw_input] listener failed to start within 3s")

    def stop(self):
        self._stop.set()
        if self._hwnd:
            try: user32.PostMessageW(self._hwnd, WM_QUIT, 0, 0)
            except Exception: pass

    def _resolve_mouse_want(self):
        # caller must hold _sub_lock
        return self._cfg_want_mouse or (self._mouse_refs > 0)

    def set_mouse_subscribed(self, want: bool):
        """Config-level mouse subscription toggle. GUI capture can still
        temporarily force it on via push/pop_mouse_ref."""
        changed = False
        with self._sub_lock:
            if want == self._cfg_want_mouse:
                return
            self._cfg_want_mouse = want
            effective = self._resolve_mouse_want()
            changed = (effective != self._applied_mouse)
        if changed:
            self._reregister_devices()

    def push_mouse_ref(self):
        """GUI: call when a key field gains focus so mb4/mb5 can be captured."""
        changed = False
        with self._sub_lock:
            self._mouse_refs += 1
            effective = self._resolve_mouse_want()
            changed = (effective != self._applied_mouse)
        if changed:
            self._reregister_devices()

    def pop_mouse_ref(self):
        """GUI: call when a key field loses focus."""
        changed = False
        with self._sub_lock:
            if self._mouse_refs > 0:
                self._mouse_refs -= 1
            effective = self._resolve_mouse_want()
            changed = (effective != self._applied_mouse)
        if changed:
            self._reregister_devices()

    def _reregister_devices(self):
        if not self._hwnd:
            return
        with self._sub_lock:
            want_kbd   = self._want_kbd
            want_mouse = self._resolve_mouse_want()
            self._applied_mouse = want_mouse

        # Build the registration array. For devices we no longer want we
        # pass RIDEV_REMOVE with hwndTarget NULL.
        devs = (RAWINPUTDEVICE * 2)()
        devs[0].usUsagePage = 0x01
        devs[0].usUsage     = 0x06   # keyboard
        if want_kbd:
            devs[0].dwFlags    = RIDEV_INPUTSINK
            devs[0].hwndTarget = self._hwnd
        else:
            devs[0].dwFlags    = RIDEV_REMOVE
            devs[0].hwndTarget = HWND(0)
        devs[1].usUsagePage = 0x01
        devs[1].usUsage     = 0x02   # mouse
        if want_mouse:
            devs[1].dwFlags    = RIDEV_INPUTSINK
            devs[1].hwndTarget = self._hwnd
        else:
            devs[1].dwFlags    = RIDEV_REMOVE
            devs[1].hwndTarget = HWND(0)
        ok = user32.RegisterRawInputDevices(devs, 2, ctypes.sizeof(RAWINPUTDEVICE))
        if DEBUG:
            print(f"[raw_input] re-register kbd={want_kbd} mouse={want_mouse} ok={bool(ok)}")

    def _run(self):
        hInstance = kernel32.GetModuleHandleW(None)
        class_name = "ALX_RI_MSGONLY_CLASS"

        # NOTE: do NOT raise this thread's priority. Preempting the game's
        # input thread causes jitter and worse aim feel. Keep NORMAL so the
        # OS treats our listener like any other background process.

        self._wndproc_ref = WNDPROC(self._wnd_proc)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._wndproc_ref
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hInstance
        wc.hIcon = 0
        wc.hCursor = 0
        wc.hbrBackground = 0
        wc.lpszMenuName = None
        wc.lpszClassName = class_name
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if atom == 0:
            err = ctypes.get_last_error()
            if err not in (0, 1410):
                print(f"[raw_input] RegisterClassW failed, err={err}")
        self._class_atom = atom

        hwnd = user32.CreateWindowExW(
            0, class_name, "ALX_RI", 0, 0, 0, 0, 0,
            HWND_MESSAGE, HANDLE(0), hInstance, None
        )
        if not hwnd:
            err = ctypes.get_last_error()
            print(f"[raw_input] CreateWindowExW failed, err={err}")
            self._ready.set()
            return
        self._hwnd = hwnd

        self._reregister_devices()

        if DEBUG:
            print(f"[raw_input] hwnd={hwnd:#x} class_atom={self._class_atom} ready")

        self._ready.set()

        msg = MSG()
        while not self._stop.is_set():
            r = user32.GetMessageW(ctypes.byref(msg), HWND(0), 0, 0)
            if r == 0 or r == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        try:
            user32.DestroyWindow(hwnd)
        except Exception:
            pass
        self._hwnd = None

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            self._handle_raw_input(lparam)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _handle_raw_input(self, hRawInput_int):
        # Fast path: one syscall into a preallocated buffer. If the device's
        # payload exceeds the buffer we lose that event (acceptable — RAWINPUT
        # for keyboard/mouse is always well under 256B).
        size = UINT(self._BUF_SIZE)
        got = user32.GetRawInputData(
            HANDLE(hRawInput_int), RID_INPUT, self._buf,
            ctypes.byref(size), self._HEADER_SIZE)
        if got == 0 or got == 0xFFFFFFFF:
            return

        ri = self._ri_ptr.contents
        dwType = ri.header.dwType

        if dwType == RIM_TYPEMOUSE:
            mm = ri.data.mouse
            # fast-skip: motion-only packets with no button changes are the
            # overwhelming majority. drop them before any python-level work.
            if mm.s.usButtonFlags == 0:
                return
            if mm.ulExtraInformation == ALX_EXTRA_INFO:
                return  # our own output, echoed back by Windows
            if self._on_mouse:
                self._on_mse(mm)
            return

        if dwType == RIM_TYPEKEYBOARD:
            kb = ri.data.keyboard
            if kb.ExtraInformation == ALX_EXTRA_INFO:
                return
            if self._on_key:
                self._on_kbd(kb)

    def _on_kbd(self, kb: RAWKEYBOARD):
        # ExtraInfo + null-cb check already done in _handle_raw_input hot path.
        is_down = (kb.Flags & RI_KEY_BREAK) == 0
        name = vk_to_name(kb.VKey)
        if DEBUG:
            print(f"[raw_input] key vk={kb.VKey:#x} ({name or '?'}) {'DN' if is_down else 'UP'}")
        if not name:
            return
        try: self._on_key(name, is_down)
        except Exception as e:
            if DEBUG: print(f"[raw_input] on_key exception: {e}")

    def _on_mse(self, mm: RAWMOUSE):
        # fast-path already filtered self events + no-button packets
        flags = mm.s.usButtonFlags
        pairs = (
            (RI_MOUSE_LEFT_BUTTON_DOWN,   "left",   True),
            (RI_MOUSE_LEFT_BUTTON_UP,     "left",   False),
            (RI_MOUSE_RIGHT_BUTTON_DOWN,  "right",  True),
            (RI_MOUSE_RIGHT_BUTTON_UP,    "right",  False),
            (RI_MOUSE_MIDDLE_BUTTON_DOWN, "middle", True),
            (RI_MOUSE_MIDDLE_BUTTON_UP,   "middle", False),
            (RI_MOUSE_BUTTON_4_DOWN,      "x1",     True),
            (RI_MOUSE_BUTTON_4_UP,        "x1",     False),
            (RI_MOUSE_BUTTON_5_DOWN,      "x2",     True),
            (RI_MOUSE_BUTTON_5_UP,        "x2",     False),
        )
        for mask, name, is_down in pairs:
            if flags & mask:
                if DEBUG:
                    print(f"[raw_input] mouse {name} {'DN' if is_down else 'UP'}")
                try: self._on_mouse(name, is_down)
                except Exception as e:
                    if DEBUG: print(f"[raw_input] on_mouse exception: {e}")
