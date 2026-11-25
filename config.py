import json
import os
import shutil
import sys
from pathlib import Path
from threading import RLock


def _persistent_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundled_template():
    if hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / "config.json"
        if p.exists():
            return p
    return None


CONFIG_PATH = _persistent_dir() / "config.json"

# -----------------------------------------------------------------------------
# DEFAULTS
#
# Build binds are a NAMED DICT (not a flat list) so every macro can reference
# a piece by role ("wall", "floor", etc.) and you only have to configure your
# Fortnite keys in ONE place. Instant builds are scripted sequences that cite
# these names — change your in-game wall bind from Q to E and every macro that
# uses "wall" auto-tracks.
# -----------------------------------------------------------------------------
DEFAULT = {
    "main": {
        "enabled": True,
        "selectButton": "LButton",
        "postEnabled": True,
        "postKey": "",
        "postDelay": 0,
        "postTrigger": "build",
        "fastTapRescueHook": True,
        "hookRescueGapMs": 3,
    },
    # Slot 0 is edit-hold. Slots 1-4 are the ORIGINAL instant-build slots:
    # each one hold-maps a key to another key (the engine's drag behavior).
    "systems": [
        {"name": "edit_hold", "key": "f", "pause": "c", "settle": 80, "on": True},
        {"name": "build_1",   "key": "",  "pause": "",  "settle": 50, "on": False},
        {"name": "build_2",   "key": "",  "pause": "",  "settle": 50, "on": False},
        {"name": "build_3",   "key": "",  "pause": "",  "settle": 50, "on": False},
        {"name": "build_4",   "key": "",  "pause": "",  "settle": 50, "on": False},
    ],
    # User-built block-sequence macros (from the BUILDER tab).
    "custom_macros": [],
    "hotkeys": {"toggle": "f8", "exit": "f9"},
    "backend": "auto",
    "humanize": {
        "enabled": True,
        "settle_jitter_ms": 6,
        "hold_jitter_ms": 3,
        "post_delay_jitter_ms": 4,
        "microjitter_ms": 2,
        "miss_chance_pct": 0.0,
        "warmup_presses": 5,
        "warmup_slowdown_ms": 8,
        "distribution": "normal",
    },
    "stealth": {
        "window_title": "ALX2.0",
        "hide_console": True,
        "generic_tray": True,
    },
    # Named build binds — the single source of truth for piece keys.
    # Everything downstream (instant builds, post-key triggers, etc.) resolves
    # piece roles against this dict.
    "build_binds": {
        "wall":    "q",
        "floor":   "x",
        "ramp":    "c",
        "roof":    "v",
        "trap":    "t",
        "pickaxe": "g",
        "edit":    "f",
    },
}


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = Path(path)
        self._lock = RLock()
        self.data = {}

        try: self.path.parent.mkdir(parents=True, exist_ok=True)
        except Exception: pass

        if not self.path.exists():
            seed = _bundled_template()
            if seed is not None:
                try:
                    shutil.copyfile(seed, self.path)
                except Exception:
                    self.data = json.loads(json.dumps(DEFAULT))
                    self.save()
                    return
            else:
                self.data = json.loads(json.dumps(DEFAULT))
                self.save()
                return

        self.load()

    def load(self):
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = json.loads(json.dumps(DEFAULT))
                try: self.save()
                except Exception: pass
                return
            self._migrate(self.data)
            self._merge_defaults(self.data, DEFAULT)

    @staticmethod
    def _migrate(data):
        """One-shot migrations for configs saved by older versions."""
        # old shape: build_binds was a flat list ["q", "x", "c", "v", "t"].
        # new shape: named dict. Map positionally if we find the old form.
        bb = data.get("build_binds")
        if isinstance(bb, list):
            names = ["wall", "floor", "ramp", "roof", "trap"]
            new_bb = {n: bb[i] for i, n in enumerate(names) if i < len(bb)}
            new_bb.setdefault("pickaxe", "g")
            new_bb.setdefault("edit", "f")
            data["build_binds"] = new_bb

        # dead features removed in this revision
        data.pop("sprint_after_edit", None)
        data.pop("pre_fire", None)
        data.pop("vision", None)
        data.pop("edit_spam", None)
        data.pop("instant_builds", None)  # sequence-based system reverted

        # ensure systems has at least slots 0-4 (edit + 4 instant builds)
        systems = data.get("systems")
        if not isinstance(systems, list) or len(systems) < 5:
            base = systems[:1] if isinstance(systems, list) and systems else [
                {"name": "edit_hold", "key": "f", "pause": "c", "settle": 80, "on": True}
            ]
            while len(base) < 5:
                i = len(base)
                base.append({"name": f"build_{i}", "key": "", "pause": "",
                             "settle": 50, "on": False})
            data["systems"] = base

    @staticmethod
    def _merge_defaults(target, defaults):
        if isinstance(defaults, dict):
            for k, v in defaults.items():
                if k not in target:
                    target[k] = json.loads(json.dumps(v))
                else:
                    Config._merge_defaults(target[k], v)

    def save(self):
        with self._lock:
            tmp = self.path.with_suffix(".json.tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
                os.replace(tmp, self.path)
            except Exception as e:
                print(f"[config] save failed: {e} (path={self.path})")

    # ---- accessors ----
    def main(self):     return self.data["main"]
    def systems(self):  return self.data["systems"]
    def slot(self, i):  return self.data["systems"][i]
    def hotkeys(self):  return self.data["hotkeys"]
    def humanize(self): return self.data["humanize"]
    def stealth(self):  return self.data["stealth"]
    def backend_name(self): return self.data.get("backend", "auto")
    def build_binds(self):
        bb = self.data.get("build_binds", {})
        return bb if isinstance(bb, dict) else {}
    def custom_macros(self):
        return self.data.setdefault("custom_macros", [])

    # ---- setters ----
    def set_slot_field(self, i, field, value):
        with self._lock:
            self.data["systems"][i][field] = value
            self.save()

    def set_main(self, field, value):
        with self._lock:
            self.data["main"][field] = value
            self.save()

    def set_humanize(self, field, value):
        with self._lock:
            self.data["humanize"][field] = value
            self.save()

    def set_stealth(self, field, value):
        with self._lock:
            self.data["stealth"][field] = value
            self.save()

    def set_build_bind(self, role: str, key: str):
        """Set one named bind, e.g. set_build_bind("wall", "q")."""
        with self._lock:
            bb = self.data.setdefault("build_binds", {})
            bb[role] = key
            self.save()

    # ---- custom macros (BUILDER tab) ----
    def set_custom_macro(self, i: int, macro: dict):
        with self._lock:
            lst = self.data.setdefault("custom_macros", [])
            while len(lst) <= i: lst.append({})
            lst[i] = macro
            self.save()

    def add_custom_macro(self, macro: dict) -> int:
        with self._lock:
            lst = self.data.setdefault("custom_macros", [])
            lst.append(macro)
            self.save()
            return len(lst) - 1

    def delete_custom_macro(self, i: int):
        with self._lock:
            lst = self.data.setdefault("custom_macros", [])
            if 0 <= i < len(lst):
                lst.pop(i)
                self.save()

