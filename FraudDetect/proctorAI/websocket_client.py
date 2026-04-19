# ─────────────────────────────────────────────────────
# websocket_client.py
# Sends all detection events to the backend in real time
# over a persistent WebSocket connection.
#
# Usage:
#   client = WebSocketClient(session_id="session_001")
#   client.start()
#   client.send(event_dict)
#   client.stop()
# ─────────────────────────────────────────────────────

import json
import time
import threading
import asyncio
import websockets
from config import WEBSOCKET_URL, SESSION_ID


class WebSocketClient:
    def __init__(self, session_id=None, url=None):
        self.session_id     = session_id or SESSION_ID
        self.url            = url or f"{WEBSOCKET_URL}/{self.session_id}"
        self.is_running     = False
        self.is_connected   = False

        # Event queue — events pile up here if connection drops
        self.queue          = []
        self.queue_lock     = threading.Lock()

        # Retry settings
        self.retry_interval = 3.0    # seconds between reconnect attempts
        self.max_retries    = 999999     # give up after 10 failed attempts

        # Stats
        self.sent_count     = 0
        self.failed_count   = 0
        self.dropped_count  = 0

        # Background thread + asyncio event loop
        self._thread        = None
        self._loop          = None
        self._ws            = None

    # ── Start background thread ──────────────────────────────────────────
    def start(self):
        self.is_running = True
        self._thread    = threading.Thread(
            target = self._run_loop,
            daemon = True,
        )
        self._thread.start()
        print(f"[WebSocketClient] Started — connecting to {self.url}")

    # ── Stop ─────────────────────────────────────────────────────────────
    def stop(self):
        self.is_running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        print(f"[WebSocketClient] Stopped — sent={self.sent_count} failed={self.failed_count}")

    # ── Send event (thread-safe, called from any module) ─────────────────
    def send(self, event: dict):
        """
        Call this from any module to send an event to the backend.
        Thread-safe — adds to queue, background thread sends it.
        """
        # Add session metadata
        event["session_id"] = self.session_id
        if "timestamp" not in event:
            event["timestamp"] = time.time()

        with self.queue_lock:
            # Drop oldest if queue gets too large (connection is down)
            if len(self.queue) > 500:
                self.queue.pop(0)
                self.dropped_count += 1
            self.queue.append(event)

    # ── Background asyncio loop ───────────────────────────────────────────
    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_and_send())

    # ── Main async connection + send loop ────────────────────────────────
    async def _connect_and_send(self):
        retries = 0
        while self.is_running:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval = 20,
                    ping_timeout  = 10,
                ) as ws:
                    self._ws          = ws
                    self.is_connected = True
                    retries           = 0
                    print(f"[WebSocketClient] Connected to {self.url}")
                    await self._send_loop(ws)

            except Exception as e:
                self.is_connected = False
                retries          += 1
                # Only print first failure and every 10th after
                if retries == 1 or retries % 10 == 0:
                    print(f"[WebSocketClient] No backend yet — retrying silently... (attempt {retries})")
            await asyncio.sleep(self.retry_interval)

    # ── Send loop — drains queue while connected ──────────────────────────
    async def _send_loop(self, ws):
        while self.is_running:
            # Drain all queued events
            with self.queue_lock:
                pending = self.queue.copy()
                self.queue.clear()

            for event in pending:
                try:
                    await ws.send(json.dumps(event))
                    self.sent_count += 1
                except Exception as e:
                    # Put failed events back in queue
                    with self.queue_lock:
                        self.queue.insert(0, event)
                    self.failed_count += 1
                    print(f"[WebSocketClient] Send failed: {e}")
                    return   # reconnect

            await asyncio.sleep(0.05)   # 50ms send cycle

    # ── Get stats ─────────────────────────────────────────────────────────
    def get_stats(self):
        return {
            "is_connected":  self.is_connected,
            "sent_count":    self.sent_count,
            "failed_count":  self.failed_count,
            "dropped_count": self.dropped_count,
            "queue_size":    len(self.queue),
            "url":           self.url,
        }