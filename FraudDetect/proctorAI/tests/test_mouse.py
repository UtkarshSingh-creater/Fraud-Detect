# ─────────────────────────────────────────────────────
# tests/test_mouse.py
# Run from inside proctorAI/:
# python tests/test_mouse.py
# Press Ctrl+C to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from biometrics.mouse import MouseMonitor


def on_event(event):
    status = "FLAGGED" if event["flagged"] else "ok"
    if event["type"] == "mouse_move":
        print(f"  [MOVE {status}] speed={event['speed']}px/s | {event['message']}")
    elif event["type"] == "mouse_click":
        print(f"  [CLICK {status}] gap={event['gap_ms']}ms | {event['message']}")


def main():
    monitor = MouseMonitor(event_callback=on_event)

    print("\n── Mouse Monitor Test ─────────────────────")
    print("  Move your mouse — speed will print here")
    print("  Move very fast — FLAGGED will appear")
    print("  Click rapidly — rapid click will appear")
    print("  Press Ctrl+C to quit\n")

    monitor.start()

    try:
        while True:
            time.sleep(5)
            stats = monitor.get_stats()
            print(f"\n  ── Stats ── clicks={stats['click_count']} avg_speed={stats['avg_speed']}px/s max={stats['max_speed']}px/s\n")
    except KeyboardInterrupt:
        monitor.stop()
        stats = monitor.get_stats()
        print(f"\n── Session Stats ───────────────────────────")
        print(f"  Click count   : {stats['click_count']}")
        print(f"  Avg speed     : {stats['avg_speed']}px/s")
        print(f"  Max speed     : {stats['max_speed']}px/s")
        print(f"  Baseline avg  : {stats['baseline_avg']}px/s")
        print(f"── Test complete ───────────────────────────\n")


if __name__ == "__main__":
    main()