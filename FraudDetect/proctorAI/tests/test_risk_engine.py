# ─────────────────────────────────────────────────────
# tests/test_risk_engine.py
# Run from inside proctorAI/:
# python tests/test_risk_engine.py
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring.risk_engine import RiskEngine


def on_risk_event(output):
    print(f"\n  ── BACKEND PAYLOAD ─────────────────────────")
    print(f"  risk_score  : {output['risk_score']}")
    print(f"  risk_level  : {output['risk_level']}")
    print(f"  confidence  : {output['confidence']}")
    print(f"  flagged     : {output['flagged_signals']}")
    print(f"  trigger     : {output['trigger_event']}")
    print(f"  ────────────────────────────────────────────\n")


def main():
    engine = RiskEngine(event_callback=on_risk_event)

    print("\n── Risk Engine Test ───────────────────────")
    print("  Phase 1: Normal events")
    print("  Phase 2: Suspicious events\n")

    # ── Phase 1: Normal events ────────────────────────────────────────
    print("  [Phase 1] Normal session...\n")
    normal_events = [
        {"type": "gaze",      "flagged": False, "x": 0.5,  "y": 0.5,  "gaze_locked": False},
        {"type": "keystroke", "flagged": False, "gap_ms": 145},
        {"type": "audio",     "flagged": False, "multiple_speakers": False, "whisper_detected": False},
        {"type": "liveness",  "flagged": False, "is_live": True,  "blink_count": 8},
        {"type": "head_pose", "flagged": False, "yaw": 5.0, "pitch": 3.0},
        {"type": "face_verify","flagged": False, "same_person": True, "confidence": 0.95},
    ]
    for e in normal_events:
        output = engine.process_event(e)
        print(f"  [{output['risk_level']}] score={output['risk_score']} confidence={output['confidence']} | {e['type']}")

    snapshot = engine.get_snapshot()
    print(f"\n  Snapshot after Phase 1:")
    print(f"  score={snapshot['risk_score']} level={snapshot['risk_level']} flagged={snapshot['flagged_signals']}\n")

    # ── Phase 2: Suspicious events ────────────────────────────────────
    print("  [Phase 2] Cheating detected...\n")
    suspicious_events = [
        {"type": "gaze",          "flagged": True, "gaze_locked": True,  "x": 0.9, "y": 0.9},
        {"type": "paste",         "flagged": True, "char_count": 850},
        {"type": "audio",         "flagged": True, "multiple_speakers": True, "whisper_detected": False},
        {"type": "multiple_faces","flagged": True, "face_count": 2},
        {"type": "gaze",          "flagged": True, "gaze_locked": True,  "x": 0.88, "y": 0.91},
        {"type": "paste",         "flagged": True, "char_count": 620},
        {"type": "deepfake",      "flagged": True, "fake_prob": 0.82, "is_synthetic": True},
        {"type": "temporal",      "flagged": True, "suspicious_prob": 0.97},
        {"type": "liveness",      "flagged": True, "is_live": False, "blink_count": 0},
        {"type": "keystroke",     "flagged": True, "gap_ms": 4},
    ]
    for e in suspicious_events:
        output = engine.process_event(e)
        print(f"  [{output['risk_level']}] score={output['risk_score']} confidence={output['confidence']} | {e['type']}")

    snapshot = engine.get_snapshot()
    print(f"\n  Snapshot after Phase 2:")
    print(f"  score={snapshot['risk_score']}")
    print(f"  level={snapshot['risk_level']}")
    print(f"  confidence={snapshot['confidence']}")
    print(f"  flagged={snapshot['flagged_signals']}")
    print(f"  counts={snapshot['signal_counts']}\n")
    print(f"── Test complete ───────────────────────────\n")


if __name__ == "__main__":
    main()