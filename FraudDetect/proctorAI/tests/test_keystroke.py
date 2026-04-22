# ─────────────────────────────────────────────────────
# tests/test_keystroke.py
# Run from inside proctorAI/:
# python tests/test_keystroke.py
# Press Ctrl+C to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from biometrics.keystroke import KeystrokeMonitor


def on_event(event):
    status = "FLAGGED" if event["flagged"] else "ok"
    if event["type"] == "paste":
        print(f"  [PASTE {status}] chars={event['char_count']} | {event['message']}")
    elif event["type"] == "keystroke":
        print(f"  [KEY {status}] gap={event['gap_ms']}ms | {event['message']}")


def main():
    monitor = KeystrokeMonitor(event_callback=on_event)

    print("\n── Keystroke Monitor Test ─────────────────")
    print("  Type anything — gaps will print here")
    print("  Try Cmd+V to test paste detection")
    print("  Press Ctrl+C to quit\n")

    monitor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        stats = monitor.get_stats()
        print(f"\n── Session Stats ───────────────────────────")
        print(f"  Total keystrokes : {stats['total_keystrokes']}")
        print(f"  Paste count      : {stats['paste_count']}")
        print(f"  Baseline avg     : {stats['baseline_avg_ms']}ms")
        print(f"── Test complete ───────────────────────────\n")


if __name__ == "__main__":
    main()