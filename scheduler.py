"""
Deadline scheduler. One worker thread services every pending callback.

Why not threading.Timer:
- Each Timer spawns a fresh thread. At settle=0 the wait(0) returns before the
  Python main thread finishes releasing the engine lock, so the Timer's
  callback races the key-up handler for that lock. Whoever loses the race
  loses the event (click skipped, or click fired with no release recorded).
- Per-call thread spawn has 1-5ms of startup noise even at nominally-zero
  intervals.

The scheduler keeps a min-heap keyed by deadline (perf_counter), one worker
thread sleeps until the next deadline, fires the callback, and loops.
Cancellation is lazy — the handle just flips a flag the worker checks when
it pops.
"""
import heapq
import itertools
import threading
import time

# Raise Windows timer resolution so condition-variable waits honor sub-15ms
# intervals. Without this, Scheduler(settle_ms=1) can fire 15.6ms late — far
# past when a fast F tap released, causing missed edits.
try:
    import ctypes
    _winmm = ctypes.WinDLL("winmm", use_last_error=True)
    _winmm.timeBeginPeriod.argtypes = (ctypes.c_uint,)
    _winmm.timeEndPeriod.argtypes = (ctypes.c_uint,)
    _winmm.timeBeginPeriod(1)
    _TIMER_PERIOD_RAISED = True
except Exception:
    _winmm = None
    _TIMER_PERIOD_RAISED = False


class Handle:
    __slots__ = ("cancelled",)
    def __init__(self):
        self.cancelled = False
    def cancel(self):
        self.cancelled = True


class Scheduler:
    def __init__(self, name="alx-scheduler"):
        self._heap = []
        self._cv = threading.Condition()
        self._stop = False
        self._counter = itertools.count()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def schedule_after_ms(self, delay_ms, callback, *args, **kwargs) -> Handle:
        deadline = time.perf_counter() + max(0.0, delay_ms) / 1000.0
        return self.schedule_at(deadline, callback, *args, **kwargs)

    def schedule_at(self, deadline, callback, *args, **kwargs) -> Handle:
        h = Handle()
        item = (deadline, next(self._counter), h, callback, args, kwargs)
        with self._cv:
            heapq.heappush(self._heap, item)
            self._cv.notify()
        return h

    def shutdown(self, timeout=1.0):
        with self._cv:
            self._stop = True
            self._cv.notify_all()
        self._thread.join(timeout=timeout)
        if _TIMER_PERIOD_RAISED and _winmm:
            try: _winmm.timeEndPeriod(1)
            except Exception: pass

    def _run(self):
        while True:
            with self._cv:
                while not self._stop and not self._heap:
                    self._cv.wait()
                if self._stop:
                    return
                deadline, _, handle, cb, args, kwargs = self._heap[0]
                now = time.perf_counter()
                wait = deadline - now
                if wait > 0:
                    self._cv.wait(timeout=wait)
                    # re-check: a sooner item may have been pushed, or stop set
                    if self._stop:
                        return
                    if not self._heap or self._heap[0][0] > deadline:
                        continue
                heapq.heappop(self._heap)
            # execute outside the cv lock
            if handle.cancelled:
                continue
            try:
                cb(*args, **kwargs)
            except Exception:
                pass
