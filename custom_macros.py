"""
Custom macro runtime — executes user-built block sequences.

A macro is a list of blocks (dicts) stored under config["custom_macros"].
Each block has a "type" and type-specific fields.

Supported block types:
    key_press       {key: str, hold_ms: int}         press & release a key
    key_down        {key: str}                       hold down a key
    key_up          {key: str}                       release a key
    click           {button: str, hold_ms: int}      mouse click
    mouse_down      {button: str}                    hold a mouse button
    mouse_up        {button: str}                    release a mouse button
    wait            {ms: int}                        sleep
    move_rel        {dx: int, dy: int}               relative mouse move
    scroll          {delta: int}                     wheel scroll
    repeat_start    {count: int}                     begin loop
    repeat_end      {}                               end loop (paired)

Each saved macro has:
    name, enabled, trigger_key, blocks

The runner wires one trigger per macro into the HotkeyRouter.
"""
from __future__ import annotations
import os
import threading
import time


DEBUG = os.environ.get("ALX_DEBUG") == "1"


class CustomMacroRunner:
    def __init__(self, cfg, backend):
        self.cfg = cfg
        self.backend = backend
        self._lock = threading.Lock()
        self._running: dict[int, bool] = {}
        self._cancel = threading.Event()

    # ---------------- public API ----------------
    def macros(self):
        return self.cfg.data.get("custom_macros", []) or []

    def trigger(self, idx: int):
        """Fire macro #idx in a background thread. Ignored if already running."""
        with self._lock:
            if not self.cfg.main().get("enabled", True):
                return
            macros = self.macros()
            if idx >= len(macros):
                return
            m = macros[idx]
            if not m.get("enabled", False):
                return
            if self._running.get(idx, False):
                return
            self._running[idx] = True
            self._cancel.clear()
        threading.Thread(target=self._run, args=(idx,),
                         daemon=True, name=f"alx-macro-{idx}").start()

    def cancel_all(self):
        self._cancel.set()

    # ---------------- internals ----------------
    def _wait(self, ms: int) -> bool:
        """Sleep, returns False if cancelled."""
        if ms <= 0:
            return not self._cancel.is_set()
        return not self._cancel.wait(ms / 1000.0)

    def _run(self, idx: int):
        try:
            m = self.macros()[idx]
            blocks = list(m.get("blocks", []) or [])
            if not blocks:
                return
            self._exec(blocks)
        except Exception as e:
            if DEBUG: print(f"[macro] #{idx} error: {e}")
        finally:
            with self._lock:
                self._running[idx] = False

    def _exec(self, blocks: list):
        """Execute a flat list, honoring repeat_start / repeat_end brackets."""
        i = 0
        n = len(blocks)
        while i < n:
            if self._cancel.is_set():
                return
            b = blocks[i] or {}
            t = str(b.get("type", "")).lower()

            if t == "repeat_start":
                # find matching repeat_end
                depth = 1
                j = i + 1
                while j < n and depth > 0:
                    tj = str(blocks[j].get("type", "")).lower()
                    if tj == "repeat_start": depth += 1
                    elif tj == "repeat_end": depth -= 1
                    if depth == 0: break
                    j += 1
                if depth != 0:
                    return  # unbalanced; bail
                inner = blocks[i + 1:j]
                count = max(1, int(b.get("count", 1)))
                for _ in range(count):
                    if self._cancel.is_set(): return
                    self._exec(inner)
                i = j + 1
                continue

            if t == "repeat_end":
                # stray — ignore
                i += 1
                continue

            self._exec_one(b, t)
            i += 1

    def _exec_one(self, b: dict, t: str):
        try:
            if t == "key_press":
                key = str(b.get("key", "")).strip()
                hold = max(0, int(b.get("hold_ms", 10)))
                if key: self.backend.send(key, hold_ms=hold)
            elif t == "key_down":
                key = str(b.get("key", "")).strip()
                if key and hasattr(self.backend, "key_down"):
                    self.backend.key_down(key)
            elif t == "key_up":
                key = str(b.get("key", "")).strip()
                if key and hasattr(self.backend, "key_up"):
                    self.backend.key_up(key)
            elif t == "click":
                btn = str(b.get("button", "LButton"))
                hold = max(0, int(b.get("hold_ms", 10)))
                self.backend.mouse_down(btn)
                if hold > 0: time.sleep(hold / 1000.0)
                self.backend.mouse_up(btn)
            elif t == "mouse_down":
                self.backend.mouse_down(str(b.get("button", "LButton")))
            elif t == "mouse_up":
                self.backend.mouse_up(str(b.get("button", "LButton")))
            elif t == "wait":
                self._wait(int(b.get("ms", 25)))
            elif t == "move_rel":
                if hasattr(self.backend, "move_rel"):
                    self.backend.move_rel(int(b.get("dx", 0)),
                                          int(b.get("dy", 0)))
            elif t == "scroll":
                if hasattr(self.backend, "scroll"):
                    self.backend.scroll(int(b.get("delta", 0)))
            elif t == "wait_key":
                # not implemented yet — treat as a short wait
                self._wait(int(b.get("ms", 50)))
        except Exception as e:
            if DEBUG: print(f"[macro] block {t} error: {e}")


# ---------------- block catalog ----------------
# Used by the GUI's BUILDER tab. Each entry: label, type, default params,
# param schema (list of (field, kind, default, label)).
BLOCK_CATALOG = [
    {
        "type": "key_press",
        "label": "Press Key",
        "icon": "⌨",
        "defaults": {"key": "a", "hold_ms": 10},
        "params": [("key", "str", "a", "Key"),
                   ("hold_ms", "int", 10, "Hold (ms)")],
        "summary": lambda b: f"Press  {b.get('key','?')}   hold {b.get('hold_ms',0)}ms",
    },
    {
        "type": "key_down",
        "label": "Hold Key Down",
        "icon": "▼",
        "defaults": {"key": "shift"},
        "params": [("key", "str", "shift", "Key")],
        "summary": lambda b: f"Hold down  {b.get('key','?')}",
    },
    {
        "type": "key_up",
        "label": "Release Key",
        "icon": "▲",
        "defaults": {"key": "shift"},
        "params": [("key", "str", "shift", "Key")],
        "summary": lambda b: f"Release  {b.get('key','?')}",
    },
    {
        "type": "click",
        "label": "Mouse Click",
        "icon": "🖱",
        "defaults": {"button": "LButton", "hold_ms": 10},
        "params": [("button", "choice:LButton,RButton,MButton", "LButton", "Button"),
                   ("hold_ms", "int", 10, "Hold (ms)")],
        "summary": lambda b: f"Click  {b.get('button','?')}   hold {b.get('hold_ms',0)}ms",
    },
    {
        "type": "mouse_down",
        "label": "Hold Mouse Down",
        "icon": "▼",
        "defaults": {"button": "LButton"},
        "params": [("button", "choice:LButton,RButton,MButton", "LButton", "Button")],
        "summary": lambda b: f"Hold  {b.get('button','?')}",
    },
    {
        "type": "mouse_up",
        "label": "Release Mouse",
        "icon": "▲",
        "defaults": {"button": "LButton"},
        "params": [("button", "choice:LButton,RButton,MButton", "LButton", "Button")],
        "summary": lambda b: f"Release  {b.get('button','?')}",
    },
    {
        "type": "wait",
        "label": "Wait",
        "icon": "⏱",
        "defaults": {"ms": 50},
        "params": [("ms", "int", 50, "Duration (ms)")],
        "summary": lambda b: f"Wait  {b.get('ms',0)}ms",
    },
    {
        "type": "move_rel",
        "label": "Move Mouse",
        "icon": "↗",
        "defaults": {"dx": 20, "dy": 0},
        "params": [("dx", "int", 20, "dx (px)"),
                   ("dy", "int", 0,  "dy (px)")],
        "summary": lambda b: f"Move  ({b.get('dx',0)}, {b.get('dy',0)})",
    },
    {
        "type": "scroll",
        "label": "Scroll Wheel",
        "icon": "⇕",
        "defaults": {"delta": 120},
        "params": [("delta", "int", 120, "Delta  (120 = 1 notch up)")],
        "summary": lambda b: f"Scroll  {b.get('delta',0)}",
    },
    {
        "type": "repeat_start",
        "label": "Repeat (start)",
        "icon": "↻",
        "defaults": {"count": 3},
        "params": [("count", "int", 3, "Times")],
        "summary": lambda b: f"Repeat × {b.get('count',1)}   →",
    },
    {
        "type": "repeat_end",
        "label": "Repeat (end)",
        "icon": "⟲",
        "defaults": {},
        "params": [],
        "summary": lambda _b: "⟵   End repeat",
    },
]


def block_meta(block_type: str) -> dict | None:
    for entry in BLOCK_CATALOG:
        if entry["type"] == block_type:
            return entry
    return None
