"""
Statistical humanization. Removes the perfect-timing fingerprint that
pattern-based cheat detection models look for. Every value runs through
one of two distributions (uniform or truncated normal) at event time.
"""
import random
import time

class Humanizer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.press_count = 0  # per-session, for warmup drift

    def _h(self):
        return self.cfg.humanize()

    def _enabled(self):
        return bool(self._h().get("enabled", True))

    def _draw(self, span):
        """Draw a jitter sample in range (-span, +span)."""
        if span <= 0:
            return 0.0
        dist = self._h().get("distribution", "normal")
        if dist == "normal":
            # truncated normal — sigma = span/2.5, clip to span
            v = random.gauss(0.0, span / 2.5)
            if v > span:  v = span
            if v < -span: v = -span
            return v
        return random.uniform(-span, span)

    # -------- public API --------
    def register_press(self):
        self.press_count += 1

    def should_miss(self):
        if not self._enabled():
            return False
        pct = float(self._h().get("miss_chance_pct", 0.0))
        if pct <= 0:
            return False
        return random.uniform(0, 100) < pct

    def settle_ms(self, base_ms):
        # Floor at 1ms. The scheduler handles 0ms correctly now, but 1ms costs
        # you nothing in-game and guarantees no race whatever the backend is.
        if not self._enabled():
            return max(1, int(base_ms))
        jitter = self._draw(float(self._h().get("settle_jitter_ms", 0)))
        warmup = self._warmup_bonus_ms()
        return max(1, int(round(base_ms + jitter + warmup)))

    def hold_ms(self, base_ms=0):
        """Extra time the click stays down beyond the natural key-hold span."""
        if not self._enabled():
            return max(0, int(base_ms))
        jitter = self._draw(float(self._h().get("hold_jitter_ms", 0)))
        return max(0, int(round(base_ms + jitter)))

    def post_delay_ms(self, base_ms):
        if not self._enabled():
            return max(0, int(base_ms))
        jitter = self._draw(float(self._h().get("post_delay_jitter_ms", 0)))
        return max(0, int(round(base_ms + jitter)))

    def microsleep(self):
        """Called immediately before any output-call. Sub-millisecond granularity."""
        if not self._enabled():
            return
        span = float(self._h().get("microjitter_ms", 0))
        if span <= 0:
            return
        # always positive, uniform in [0, span)
        time.sleep(random.uniform(0, span) / 1000.0)

    # -------- internals --------
    def _warmup_bonus_ms(self):
        n = int(self._h().get("warmup_presses", 0))
        s = float(self._h().get("warmup_slowdown_ms", 0))
        if n <= 0 or s <= 0:
            return 0.0
        if self.press_count >= n:
            return 0.0
        # linear decay from s down to 0 over first n presses
        remaining = (n - self.press_count) / n
        return s * remaining
