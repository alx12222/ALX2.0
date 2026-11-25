"""
Dispatch layer: RawInputListener events -> engine calls.

Also owns the two global hotkeys (toggle, exit) and the GUI capture bridge.
The capture callback can consume the event (return True) so a mouse button
being captured into a key field does NOT also fire its old binding.
"""
import threading

MOUSE_ALIASES = {
    "mb4": "x1", "mb5": "x2",
    "xbutton1": "x1", "xbutton2": "x2",
    "mouse_x1": "x1", "mouse_x2": "x2",
    "mouse_left": "left", "mouse_right": "right", "mouse_middle": "middle",
    "lbutton": "left", "rbutton": "right", "mbutton": "middle",
    "left": "left", "right": "right", "middle": "middle",
}
NAME_TO_DISPLAY = {
    "x1": "mb4", "x2": "mb5",
    "left": "LButton", "right": "RButton", "middle": "MButton",
}


def _normalize(name: str):
    if not name: return ("", "")
    n = name.strip().lower()
    if n in MOUSE_ALIASES:
        return ("mouse", MOUSE_ALIASES[n])
    return ("key", n)


class HotkeyRouter:
    def __init__(self, engine, cfg, on_toggle, on_exit, listener=None,
                 custom_macros=None, **_kw):
        self.engine = engine
        self.cfg = cfg
        self.on_toggle = on_toggle
        self.on_exit = on_exit
        self._listener = listener
        self._macros = custom_macros
        self._capture_cb = None
        self._lock = threading.Lock()
        self._table = {}
        self.rebuild()

    def set_listener(self, listener):
        self._listener = listener
        self.rebuild()

    def set_capture_cb(self, cb):
        """cb(display_name) -> bool; if truthy, event is consumed (no dispatch)."""
        with self._lock:
            self._capture_cb = cb

    def rebuild(self):
        with self._lock:
            self._table = {}

            def add(kn, edge, cb):
                self._table.setdefault(kn, []).append((edge, cb))

            for i, s in enumerate(self.cfg.systems()):
                on = bool(s.get("on", True))
                k = s.get("key") or ""
                p = s.get("pause") or ""
                register_key = on or (i == 0 and k)
                if register_key and k:
                    kn = _normalize(k)
                    if kn[1]:
                        add(kn, "down", (lambda i=i: self.engine.on_slot_down(i)))
                        add(kn, "up",   (lambda i=i: self.engine.on_slot_up(i)))
                if on and p:
                    pn = _normalize(p)
                    if pn[1]:
                        add(pn, "down", (lambda i=i: self.engine.on_pause(i)))

            hk = self.cfg.hotkeys()
            tog = _normalize(hk.get("toggle", "f8"))
            ext = _normalize(hk.get("exit",   "f9"))
            if tog[1]: add(tog, "down", self.on_toggle)
            if ext[1]: add(ext, "down", self.on_exit)

            # Build binds + left click: build bind ARMS; the post key fires
            # on the next physical left-click RELEASE (so the piece commits
            # before the key lands). Only register when post key is enabled
            # with trigger "build" or "both".
            main = self.cfg.main()
            trigger = (main.get("postTrigger") or "build").lower()
            post_on   = bool(main.get("postEnabled") and (main.get("postKey") or ""))
            post_wants_build = post_on and trigger in ("build", "both")

            # also check: any slot bound to a mouse button needs mouse sub
            any_slot_mouse = any(
                _normalize(s.get("key") or "")[0] == "mouse" or
                _normalize(s.get("pause") or "")[0] == "mouse"
                for s in self.cfg.systems()
            )

            # custom macro triggers
            macro_triggers = []
            if self._macros is not None:
                for idx, m in enumerate(self.cfg.custom_macros()):
                    if not m.get("enabled"): continue
                    tk = m.get("trigger_key") or ""
                    tn = _normalize(tk)
                    if tn[1]:
                        macro_triggers.append((idx, tn))
            macro_needs_mouse = any(tn[0] == "mouse" for _, tn in macro_triggers)

            needs_mouse = post_wants_build or any_slot_mouse or macro_needs_mouse

            for idx, tn in macro_triggers:
                add(tn, "down", (lambda i=idx: self._macros.trigger(i)))

            if post_wants_build:
                # build_binds is a dict {role: key}; iterate over the key values
                binds = self.cfg.build_binds() or {}
                values = binds.values() if isinstance(binds, dict) else binds
                for bind in values:
                    bn = _normalize(bind)
                    if bn[1]:
                        add(bn, "down",
                            (lambda name=bind: self.engine.on_build_bind_down(name)))
                add(("mouse", "left"), "down",
                    (lambda: self.engine.on_physical_left_click()))
                add(("mouse", "left"), "up",
                    (lambda: self.engine.on_physical_left_release()))


            # tell the listener whether we need the mouse at all. when False,
            # thousands of mouse-motion packets per second get skipped at
            # the Windows raw-input device level — big aim-feel win.
            if self._listener is not None:
                try: self._listener.set_mouse_subscribed(needs_mouse)
                except Exception: pass

    # -------- from listener thread --------
    def on_key_event(self, name, is_down):
        self._dispatch(("key", name), is_down)

    def on_mouse_event(self, button, is_down):
        # capture takes priority on mb4/mb5 down events
        if is_down and button in ("x1", "x2"):
            cb = None
            with self._lock:
                cb = self._capture_cb
            if cb:
                try:
                    if cb(NAME_TO_DISPLAY.get(button, button)):
                        return  # consumed
                except Exception:
                    pass
        self._dispatch(("mouse", button), is_down)

    def _dispatch(self, kn, is_down):
        edge = "down" if is_down else "up"
        with self._lock:
            handlers = list(self._table.get(kn, ()))
        for e, cb in handlers:
            if e == edge:
                try: cb()
                except Exception: pass
