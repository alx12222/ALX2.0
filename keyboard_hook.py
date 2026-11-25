"""
Low-level keyboard hook — the only reliable way to intercept F-up BEFORE
Fortnite exits edit mode and insert the click confirm.

Flow when rescue triggers:
    user physically releases F
      -> hook sees F-up event FIRST (before game, before raw input)
      -> hook checks engine: HOLDING + !click_sent + !missed  =>  rescue
      -> send LMB-down   (SendInput, injected)
      -> brief sleep     (so game processes it as a click, not a flicker)
      -> send LMB-up     (SendInput, injected)
      -> return 1        (SUPPRESS the F-up — game never sees it)
      -> inject a synthetic F-up via SendInput so game exits edit cleanly
      -> explicitly transition engine state (physical F-up was suppressed)

Our own injected events carry ALX_EXTRA_INFO; the hook ignores them so we
don't loop. The raw-input listener also filters them.
"""
import ctypes
import ctypes.wintypes as wt
import threading
import time
import os

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DEBUG = os.environ.get("ALX_DEBUG") == "1"

WH_KEYBOARD_LL = 13
WM_KEYUP      = 0x0101
WM_SYSKEYUP   = 0x0105

LLKHF_INJECTED = 0x00000010
ALX_EXTRA_INFO = 0xA7CBA070   # must match input_backend / raw_input

LRESULT   = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode",       wt.DWORD),
        ("scanCode",     wt.DWORD),
        ("flags",        wt.DWORD),
        ("time",         wt.DWORD),
        ("dwExtraInfo",  ULONG_PTR),
    ]

LowLevelKeyboardProc = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)

user32.SetWindowsHookExW.argtypes = (ctypes.c_int, LowLevelKeyboardProc,
                                     wt.HINSTANCE, wt.DWORD)
user32.SetWindowsHookExW.restype  = wt.HANDLE
user32.CallNextHookEx.argtypes = (wt.HANDLE, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.CallNextHookEx.restype  = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wt.HANDLE,)
user32.UnhookWindowsHookEx.restype  = wt.BOOL
user32.PostThreadMessageW.argtypes = (wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.PostThreadMessageW.restype  = wt.BOOL

kernel32.GetModuleHandleW.argtypes = (wt.LPCWSTR,)
kernel32.GetModuleHandleW.restype  = wt.HINSTANCE
kernel32.GetCurrentThreadId.argtypes = ()
kernel32.GetCurrentThreadId.restype  = wt.DWORD

WM_QUIT = 0x0012

class _POINT(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG)]
class _MSG(ctypes.Structure):
    _fields_ = [("hwnd", wt.HWND), ("message", wt.UINT),
                ("wParam", wt.WPARAM), ("lParam", wt.LPARAM),
                ("time", wt.DWORD), ("pt", _POINT)]


class KeyboardHook:
    """Low-level keyboard hook that rescues missed edits by sending a
    synchronous click burst in front of a too-fast F-up."""

    def __init__(self, engine, cfg, backend):
        self.engine = engine
        self.cfg = cfg
        self.backend = backend
        self._proc_ref = None   # keep callback alive
        self._handle = None
        self._thread_id = None
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread_id:
            try: user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception: pass

    def _run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        self._proc_ref = LowLevelKeyboardProc(self._proc)
        hInstance = kernel32.GetModuleHandleW(None)
        self._handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc_ref, hInstance, 0)
        if not self._handle:
            if DEBUG:
                err = ctypes.get_last_error()
                print(f"[kbhook] SetWindowsHookExW failed err={err}")
            return
        if DEBUG:
            print(f"[kbhook] installed, tid={self._thread_id}")
        msg = _MSG()
        while True:
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r in (0, 0xFFFFFFFF): break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        try: user32.UnhookWindowsHookEx(self._handle)
        except Exception: pass
        self._handle = None

    def _proc(self, nCode, wParam, lParam):
        if nCode >= 0 and wParam in (WM_KEYUP, WM_SYSKEYUP):
            try:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                # our own synthetic events get skipped
                if kb.dwExtraInfo != ALX_EXTRA_INFO:
                    if self._handle_up(kb):
                        return 1   # suppress — game must NOT see this F-up
            except Exception as e:
                if DEBUG: print(f"[kbhook] proc exception: {e}")
        return user32.CallNextHookEx(self._handle, nCode, wParam, lParam)

    def _handle_up(self, kb: KBDLLHOOKSTRUCT) -> bool:
        """Return True if we're rescuing (and the F-up must be suppressed)."""
        # import locally to avoid cycle at import time
        from raw_input import vk_to_name
        name = vk_to_name(kb.vkCode)
        edit_key = (self.cfg.slot(0).get("key") or "").lower()
        if not name or name != edit_key:
            return False

        main = self.cfg.main()
        if not main.get("fastTapRescueHook", True):
            return False

        # claim the rescue atomically with the engine
        with self.engine.lock:
            STATE_HOLDING = 1
            if self.engine.states[0] != STATE_HOLDING:
                return False
            if self.engine.click_sent[0]:
                return False
            if self.engine.missed[0]:
                return False
            # mark click_sent so a late settle timer bails
            self.engine.click_sent[0] = True

        sel = main.get("selectButton", "LButton")
        gap_ms = max(0, int(main.get("hookRescueGapMs", 3)))
        if DEBUG:
            print(f"[kbhook] RESCUE click burst gap={gap_ms}ms (vk={kb.vkCode:#x})")

        # synchronous: these go through SendInput (same backend path),
        # tagged with ALX_EXTRA_INFO so neither hook nor raw-input re-process
        self.backend.mouse_down(sel)
        if gap_ms > 0:
            time.sleep(gap_ms / 1000.0)
        self.backend.mouse_up(sel)

        # inject a synthetic F-up so the game exits edit cleanly. (Our raw
        # input listener filters ALX_EXTRA_INFO events, so this doesn't
        # loop back through the engine.)
        try:
            self.backend.key_up(edit_key)
        except Exception: pass

        # transition the engine ourselves since the physical F-up is being
        # suppressed and raw-input won't see it. _rescue_done=True so the
        # engine doesn't send a second mouse_up.
        try:
            self.engine.on_slot_up(0, _rescue_done=True)
        except Exception: pass
        return True
