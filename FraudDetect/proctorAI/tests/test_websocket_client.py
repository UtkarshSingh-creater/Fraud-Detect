# ─────────────────────────────────────────────────────
# tests/test_websocket_client.py
# Tests WebSocket client WITHOUT needing a real backend
# Uses a local mock WebSocket server
# Run from inside proctorAI/:
# python tests/test_websocket_client.py
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import json
import time
import threading
import websockets
from websocket_client import WebSocketClient


# ── Mock backend server ───────────────────────────────
async def mock_server(websocket):
    print(f"  [MockServer] Client connected")
    async for message in websocket:
        data = json.loads(message)
        print(
            f"  [MockServer] Received: "
            f"type={data.get('trigger_event')} "
            f"score={data.get('risk_score')} "
            f"level={data.get('risk_level')}"
        )


def run_mock_server():
    async def _serve():
        async with websockets.serve(mock_server, "localhost", 8000):
            await asyncio.Future()   # run forever
    asyncio.run(_serve())


def main():
    print("\n── WebSocket Client Test ──────────────────")
    print("  Starting mock backend server on ws://localhost:8000")
    print("  Sending 10 test events\n")

    # Start mock server in background
    server_thread = threading.Thread(target=run_mock_server, daemon=True)
    server_thread.start()
    time.sleep(1.0)   # wait for server to start

    # Start client
    client = WebSocketClient(
        session_id = "test_session_001",
        url        = "ws://localhost:8000/test_session_001",
    )
    client.start()
    time.sleep(1.0)   # wait for connection

    # Send 10 test events
    test_events = [
        {"type": "risk_score", "risk_score": 45, "risk_level": "MEDIUM",
         "trigger_event": "gaze", "confidence": 0.7},
        {"type": "risk_score", "risk_score": 60, "risk_level": "MEDIUM",
         "trigger_event": "paste", "confidence": 0.8},
        {"type": "risk_score", "risk_score": 75, "risk_level": "HIGH",
         "trigger_event": "banned_object", "confidence": 0.9},
        {"type": "risk_score", "risk_score": 80, "risk_level": "HIGH",
         "trigger_event": "audio", "confidence": 0.95},
        {"type": "risk_score", "risk_score": 85, "risk_level": "HIGH",
         "trigger_event": "process", "confidence": 1.0},
    ]

    for event in test_events:
        client.send(event)
        print(f"  [Client] Queued: {event['trigger_event']} score={event['risk_score']}")
        time.sleep(0.5)

    time.sleep(2.0)   # wait for all events to send

    stats = client.get_stats()
    print(f"\n── Session Stats ───────────────────────────")
    print(f"  Connected  : {stats['is_connected']}")
    print(f"  Sent       : {stats['sent_count']}")
    print(f"  Failed     : {stats['failed_count']}")
    print(f"  Queue size : {stats['queue_size']}")
    print(f"── Test complete ───────────────────────────\n")

    client.stop()


if __name__ == "__main__":
    main()