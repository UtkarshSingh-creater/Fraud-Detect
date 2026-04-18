# ─────────────────────────────────────────────────────
# tests/test_audio.py
# Run from inside proctorAI/:
# python tests/test_audio.py
# Press Ctrl+C to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from audio.audio_monitor import AudioMonitor


def on_event(event):
    status = "FLAGGED" if event["flagged"] else "ok"
    print(
        f"  [{status}] "
        f"energy={event['rms_energy']} "
        f"speech={event['is_speech']} "
        f"speakers={event['speaker_count']} "
        f"whisper={event['whisper_detected']} "
        f"| {event['message']}"
    )


def main():
    monitor = AudioMonitor(event_callback=on_event)

    print("\n── Audio Monitor Test ─────────────────────")
    print("  Speak normally — energy will print here")
    print("  Whisper — whisper detection will trigger")
    print("  Make a loud noise — anomaly will trigger")
    print("  Press Ctrl+C to quit\n")

    monitor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        stats = monitor.get_stats()
        print(f"\n── Session Stats ───────────────────────────")
        print(f"  Avg energy     : {stats['avg_energy']}")
        print(f"  Baseline energy: {stats['baseline_energy']}")
        print(f"  Voice samples  : {stats['voice_samples']}")
        print(f"── Test complete ───────────────────────────\n")


if __name__ == "__main__":
    main()