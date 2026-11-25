"""
Standalone diagnostic — run this to prove the raw-input listener is receiving
events on your machine. No config, no engine, no backend — just the listener.

Usage:
    python test_listener.py

Press keys and mouse buttons. You should see events print immediately.
Ctrl+C to quit.
"""
import os, time
os.environ["ALX_DEBUG"] = "1"

from raw_input import RawInputListener

def on_key(name, is_down):
    print(f"  KEY   {name:12s} {'DOWN' if is_down else 'UP'}")

def on_mouse(button, is_down):
    print(f"  MOUSE {button:12s} {'DOWN' if is_down else 'UP'}")

lis = RawInputListener()
lis.set_on_key(on_key)
lis.set_on_mouse(on_mouse)
lis.start()
print("Listener started. Press keys / mouse buttons. Ctrl+C to quit.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nstopping...")
    lis.stop()
    time.sleep(0.2)
