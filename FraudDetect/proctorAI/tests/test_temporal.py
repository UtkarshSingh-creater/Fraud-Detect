# ─────────────────────────────────────────────────────
# tests/test_temporal.py
# Run from inside proctorAI/:
# python tests/test_temporal.py
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from ml_models.temporal_analyzer import TemporalAnalyzer


def on_event(event):
    status = "FLAGGED" if event["flagged"] else "ok"
    print(
        f"  [{status}] "
        f"prob={event['suspicious_prob']} "
        f"events={event['events_analyzed']} "
        f"pattern='{event['pattern']}' "
        f"| {event['message']}"
    )


def main():
    analyzer = TemporalAnalyzer(
    event_callback = on_event,
    weights_path   = "ml_models/weights/temporal_lstm.pth",
)

    print("\n── Temporal Analyzer Test ─────────────────")
    print("  Simulating normal then suspicious events")
    print("  Analysis runs every 10 seconds\n")

    # Reduce interval for testing
    analyzer.check_interval = 5
    analyzer.start()

    print("  [Phase 1] Feeding normal events...")
    normal_events = [
        {"type": "gaze",      "flagged": False, "x": 0.5,  "y": 0.5},
        {"type": "keystroke", "flagged": False, "gap_ms": 150},
        {"type": "audio",     "flagged": False, "multiple_speakers": False},
        {"type": "gaze",      "flagged": False, "x": 0.48, "y": 0.51},
        {"type": "keystroke", "flagged": False, "gap_ms": 130},
        {"type": "liveness",  "flagged": False, "blink_count": 5},
        {"type": "head_pose", "flagged": False, "yaw": 5.0},
        {"type": "gaze",      "flagged": False, "x": 0.52, "y": 0.49},
        {"type": "keystroke", "flagged": False, "gap_ms": 160},
        {"type": "audio",     "flagged": False, "multiple_speakers": False},
    ]
    for e in normal_events:
        analyzer.add_event(e)

    time.sleep(7)

    print("\n  [Phase 2] Feeding suspicious events...")
    suspicious_events = []

    # 50 suspicious events to fill the window properly
    for i in range(50):
        roll = i % 5
        if roll == 0:
            suspicious_events.append({"type": "gaze",    "flagged": True, "gaze_locked": True, "x": 0.9, "y": 0.9})
        elif roll == 1:
            suspicious_events.append({"type": "paste",   "flagged": True, "char_count": 850})
        elif roll == 2:
            suspicious_events.append({"type": "audio",   "flagged": True, "multiple_speakers": True})
        elif roll == 3:
            suspicious_events.append({"type": "process", "flagged": True, "process_name": "ChatGPT"})
        else:
            suspicious_events.append({"type": "paste",   "flagged": True, "char_count": 720})
        analyzer.add_event(suspicious_events[-1])   # add only the latest event

    time.sleep(7)

    analyzer.stop()
    stats = analyzer.get_stats()
    print(f"\n── Session Stats ───────────────────────────")
    print(f"  Total analyses  : {stats['total_analyses']}")
    print(f"  Suspicious count: {stats['suspicious_count']}")
    print(f"  Buffer size     : {stats['buffer_size']}")
    print(f"── Test complete ───────────────────────────\n")


if __name__ == "__main__":
    main()