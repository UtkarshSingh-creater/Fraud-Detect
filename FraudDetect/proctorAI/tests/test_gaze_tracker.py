# ─────────────────────────────────────────────────────
# tests/test_gaze_tracker.py
# Run: python tests/test_gaze_tracker.py
# Press Q to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
from vision.gaze_tracker import GazeTracker

def main():
    cap     = cv2.VideoCapture(0)
    tracker = GazeTracker()

    print("\n── Gaze Tracker Test ──────────────────────")
    print("  Look around — gaze coords will print here")
    print("  Press Q in the video window to quit\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Cannot access webcam.")
            break

        # Get events
        events = tracker.process_frame(frame)
        for e in events:
            status = "FLAGGED" if e["flagged"] else "ok"
            print(f"  [{status}] x={e['x']} y={e['y']} | {e['message']}")

        # Draw debug overlay
        frame = tracker.draw_debug(frame)
        cv2.imshow("Gaze Tracker Test — press Q to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    tracker.release()
    cap.release()
    cv2.destroyAllWindows()
    print("\n── Test complete ──────────────────────────\n")

if __name__ == "__main__":
    main()