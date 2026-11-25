"""
Standalone diagnostic for the output path. Clicks the left mouse button once,
3 seconds after you run it — put focus on something that will react
(notepad window, browser URL bar, anything that takes a click).

Usage:
    python test_backend.py

Prints which backend was loaded. If it says 'interception', the click comes
through the Interception driver (no injected flag). If 'sendinput', it's
user-mode mouse_event.
"""
import time
import input_backend

bk = input_backend.make_backend("auto")
print(f"[test] backend: {bk.name}")
print("[test] clicking LButton in 3 seconds — focus the target window now")
for i in range(3, 0, -1):
    print(f"  {i}...")
    time.sleep(1)

bk.mouse_down("LButton")
time.sleep(0.05)
bk.mouse_up("LButton")
print("[test] click sent")
