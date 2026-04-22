# ─────────────────────────────────────────────────────
# tests/test_window_monitor.py
# Run from inside proctorAI/:
# python tests/test_window_monitor.py
# Switch between apps to test
# Press Ctrl+C to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from biometrics.window_monitor import WindowMonitor


def on_event(event):
    status = "FLAGGED" if event["flagged"] else "ok"
    print(
        f"  [{status}] "
        f"app='{event['app_name']}' "
        f"switch=#{event['switch_count']} "
        f"| {event['message']}"
    )


def main():
    monitor = WindowMonitor(event_callback=on_event)

    print("\n── Window Monitor Test ────────────────────")
    print("  Switch between apps to test detection")
    print("  Open Chrome/Safari — should flag")
    print("  Press Ctrl+C to quit\n")

    monitor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        stats = monitor.get_stats()
        print(f"\n── Session Stats ───────────────────────────")
        print(f"  Total switches : {stats['switch_count']}")
        print(f"  Last app       : {stats['last_app']}")
        print(f"── Test complete ───────────────────────────\n")


if __name__ == "__main__":
    main()