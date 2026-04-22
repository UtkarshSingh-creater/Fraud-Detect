# ─────────────────────────────────────────────────────
# tests/test_liveness.py
# Run from inside proctorAI/:
# python tests/test_liveness.py
# Press Q to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
from vision.liveness import LivenessDetector

def main():
    cap      = cv2.VideoCapture(0)
    detector = LivenessDetector()

    print("\n── Liveness Detection Test ────────────────")
    print("  Blink normally — blink count will increase")
    print("  Stay very still — FLAGGED will appear")
    print("  Press Q in video window to quit\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Cannot access webcam.")
            break

        events = detector.process_frame(frame)
        for e in events:
            status = "FLAGGED" if e["flagged"] else "ok"
            print(f"  [{status}] blinks={e['blink_count']} rate={e['blink_rate']}/min EAR={e['avg_ear']} | {e['message']}")

        frame = detector.draw_debug(frame)
        cv2.imshow("Liveness Test — press Q to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    detector.release()
    cap.release()
    cv2.destroyAllWindows()
    print("\n── Test complete ──────────────────────────\n")

if __name__ == "__main__":
    main()