"""
Core state machine for the edit-hold (drag-edit) system.

Slot 0 is the edit-hold system: hold the edit key, wait `settle` ms, auto
LMB click to confirm the edit, release click when the key is released.
That's it — instant builds are their own module now.

Per-slot state:
  states[i]       : IDLE | HOLDING | PAUSED
  downs[i]        : physical-key tracking (survives on==false)
  missed[i]       : this press rolled a humanized miss
  click_sent[i]   : whether we actually sent the mouse_down for this press
                    (so we never fire a stray mouse_up when release beats the
                     scheduled click)
"""
import os
import threading
import time

from scheduler import Scheduler

STATE_IDLE    = 0
STATE_HOLDING = 1
STATE_PAUSED  = 2

DEBUG = os.environ.get("ALX_DEBUG") == "1"

# Engine still allocates 5 state slots so existing code paths and tests
# that reference slot indices don't break. Only slot 0 is actually driven.
_SLOTS = 5


class Engine:
    def __init__(self, cfg, backend, humanizer, on_state_change=None):
        self.cfg = cfg
        self.backend = backend
        self.hu = humanizer
        self.on_state_change = on_state_change or (lambda: None)

        self.states     = [STATE_IDLE] * _SLOTS
        self.downs      = [False] * _SLOTS
        self.missed     = [False] * _SLOTS
        self.click_sent = [False] * _SLOTS
        self.settle_handles = [None] * _SLOTS
        self.post_handle = None

        # armed_post_build: set when a build bind is pressed. Cleared on the
        # left-click DOWN (which arms the post-key-on-release pending flag).
        self.armed_post_build = False
        # pending_post_release: set between left-click DOWN (which committed
        # us to firing post key) and left-click UP (where post key actually
        # fires). Keeps post key from landing while the mouse button is held.
        self.pending_post_release = False

        self.scheduler = Scheduler()
        self.lock = threading.Lock()

    @property
    def enabled(self):
        return self.cfg.main().get("enabled", True)

    def set_enabled(self, value: bool):
        self.cfg.set_main("enabled", bool(value))
        if not value:
            self._release_all()
        self._fire_state_change()

    def toggle(self):
        self.set_enabled(not self.enabled)

    def status(self):
        with self.lock:
            holding = sum(1 for s in self.states if s == STATE_HOLDING)
            paused  = sum(1 for s in self.states if s == STATE_PAUSED)
        if not self.enabled:
            return "OFF"
        if holding:
            return f"HOLDING x{holding}"
        if paused:
            return f"PAUSED x{paused}"
        return "IDLE"

    def shutdown(self):
        try: self.scheduler.shutdown()
        except Exception: pass

    # ---------- events ----------
    def on_slot_down(self, i: int):
        changed = False
        scheduled_settle = None
        with self.lock:
            s = self.cfg.slot(i)
            if not self.enabled:
                return
            if self.downs[i]:
                return
            self.downs[i] = True
            if not s.get("on", True):
                return
            if self.states[i] == STATE_HOLDING:
                return

            self.states[i] = STATE_HOLDING
            self.click_sent[i] = False
            self._cancel_settle(i)

            if i == 0:
                self.armed_post_build = False
                self.pending_post_release = False

            self.hu.register_press()
            miss = self.hu.should_miss()
            self.missed[i] = miss
            if not miss:
                settle = self.hu.settle_ms(int(s.get("settle", 80)))
                scheduled_settle = settle
                self.settle_handles[i] = self.scheduler.schedule_after_ms(
                    settle, self._do_click, i)
            changed = True

        if DEBUG:
            print(f"[engine] slot{i} DOWN  settle={scheduled_settle}ms")
        if changed:
            self._fire_state_change()

    def on_slot_up(self, i: int, _rescue_done: bool = False):
        """
        _rescue_done=True: the keyboard-hook rescue already sent BOTH mouse_down
        and mouse_up for this press, so we must NOT release again.
        """
        is_edit_slot = False
        was_click_sent = False
        with self.lock:
            if not self.downs[i] and self.states[i] == STATE_IDLE:
                return
            self.downs[i] = False
            self._cancel_settle(i)
            was_click_sent = self.click_sent[i]
            # Only release the mouse if we actually sent the mouse_down for
            # this press AND the rescue path didn't already release it.
            if (self.states[i] == STATE_HOLDING
                    and self.click_sent[i]
                    and not _rescue_done):
                self._release_click()
            self.states[i] = STATE_IDLE
            self.missed[i] = False
            self.click_sent[i] = False
            is_edit_slot = (i == 0)
        if DEBUG:
            print(f"[engine] slot{i} UP    click_was_sent={was_click_sent}  rescue_done={_rescue_done}")
        self._fire_state_change()
        if is_edit_slot:
            trigger = (self.cfg.main().get("postTrigger") or "build").lower()
            if trigger in ("edit", "both"):
                self._fire_post_build()
                # consume any pending arm so the next click doesn't fire again
                with self.lock:
                    self.armed_post_build = False
                    self.pending_post_release = False

    def on_pause(self, i: int):
        changed = False
        with self.lock:
            s = self.cfg.slot(i)
            if not self.enabled or not s.get("on", True):
                return
            if self.states[i] != STATE_HOLDING:
                return
            self._cancel_settle(i)
            if self.click_sent[i]:
                self._release_click()
            self.states[i] = STATE_PAUSED
            self.click_sent[i] = False
            changed = True
        if changed:
            self._fire_state_change()

    # ---------- internals ----------
    def _cancel_settle(self, i: int):
        h = self.settle_handles[i]
        if h is not None:
            h.cancel()
            self.settle_handles[i] = None

    def _do_click(self, i: int):
        with self.lock:
            if self.states[i] != STATE_HOLDING:
                if DEBUG: print(f"[engine] slot{i} CLICK skipped — state changed before settle fired")
                return
            if self.missed[i]:
                if DEBUG: print(f"[engine] slot{i} CLICK skipped — humanized miss")
                return
            if self.click_sent[i]:
                return
            self.click_sent[i] = True
            self.hu.microsleep()
            self.backend.mouse_down(self._sel())
            if DEBUG: print(f"[engine] slot{i} CLICK sent (mouse_down)")

    def _release_click(self):
        # caller holds self.lock
        self.hu.microsleep()
        self.backend.mouse_up(self._sel())

    def _fire_post_build(self):
        """Post key fires after ANY build bind is pressed (was: after edit release)."""
        main = self.cfg.main()
        if not (self.enabled and main.get("postEnabled") and main.get("postKey")):
            return
        delay = self.hu.post_delay_ms(int(main.get("postDelay", 0)))
        if self.post_handle is not None:
            self.post_handle.cancel()
        self.post_handle = self.scheduler.schedule_after_ms(delay, self._do_post)

    def _do_post(self):
        key = self.cfg.main().get("postKey", "")
        if not key:
            return
        hold = self.hu.hold_ms(30)
        self.hu.microsleep()
        self.backend.send(key, hold_ms=hold)

    def _release_all(self):
        with self.lock:
            for i in range(_SLOTS):
                self._cancel_settle(i)
                if self.states[i] == STATE_HOLDING and self.click_sent[i]:
                    self.backend.mouse_up(self._sel())
                self.states[i] = STATE_IDLE
                self.downs[i] = False
                self.missed[i] = False
                self.click_sent[i] = False
            self.armed_post_build = False
            self.pending_post_release = False

    def on_build_bind_down(self, physical_name: str):
        """Build bind only ARMS the post-build trigger. The actual post key
        fires on the next physical left-click release."""
        self.armed_post_build = True

    def on_physical_left_click(self):
        """Left-click DOWN. If armed and no slot is HOLDING, mark post key
        as pending — the key won't actually be sent until the player releases
        left click (so the build piece commits first)."""
        with self.lock:
            if any(st == STATE_HOLDING for st in self.states):
                return  # macro's own click during edit hold; ignore
            if not self.armed_post_build:
                return
            self.armed_post_build = False
            trigger = (self.cfg.main().get("postTrigger") or "build").lower()
            if trigger in ("build", "both"):
                self.pending_post_release = True

    def on_physical_left_release(self):
        """Left-click UP. If a post key was pended by the previous down,
        fire it now."""
        with self.lock:
            if not self.pending_post_release:
                return
            self.pending_post_release = False
        self._fire_post_build()

    def _sel(self):
        return self.cfg.main().get("selectButton", "LButton")

    def _fire_state_change(self):
        try: self.on_state_change()
        except Exception: pass
