import json
import time
import threading
import asyncio
import websockets
from config import WEBSOCKET_URL, SESSION_ID, AGENT_API_KEY


class WebSocketClient:
    def __init__(self, session_id=None, url=None):
        self.session_id   = session_id or SESSION_ID
        # FIX 1: api_key added to URL
        self.url          = url or f"{WEBSOCKET_URL}/{self.session_id}?api_key={AGENT_API_KEY}"
        self.is_running   = False
        self.is_connected = False
        self.queue        = []
        self.queue_lock   = threading.Lock()
        self.retry_interval = 3.0
        self.max_retries    = 999999
        self.sent_count     = 0
        self.failed_count   = 0
        self.dropped_count  = 0
        self._thread = None
        self._loop   = None
        self._ws     = None

    def start(self):
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[WebSocketClient] Started — connecting to {self.url}")

    def stop(self):
        self.is_running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        print(f"[WebSocketClient] Stopped — sent={self.sent_count} failed={self.failed_count}")

    def send(self, event: dict):
        event["session_id"] = self.session_id
        if "timestamp" not in event:
            event["timestamp"] = time.time()
        with self.queue_lock:
            if len(self.queue) > 500:
                self.queue.pop(0)
                self.dropped_count += 1
            # FIX 2: serialize before queuing — fixes bool/numpy crash
            self.queue.append(self._make_serializable(event))

    # FIX 2: serialization helper — converts numpy/bool to JSON-safe types
    def _make_serializable(self, obj):
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(i) for i in obj]
        elif hasattr(obj, 'flat'):        # numpy array
            return float(obj.flat[0])
        elif hasattr(obj, 'item'):        # numpy scalar
            return obj.item()
        elif isinstance(obj, bool):
            return bool(obj)
        elif isinstance(obj, float) and (obj != obj):   # NaN
            return 0.0
        return obj

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_and_send())
        except RuntimeError:
            pass
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _connect_and_send(self):
        retries = 0
        while self.is_running:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval = 20,
                    ping_timeout  = 10,
                    close_timeout = 5,       # FIX 3: stops "no close frame" spam
                ) as ws:
                    self._ws          = ws
                    self.is_connected = True
                    retries           = 0
                    print(f"[WebSocketClient] Connected to {self.url}")
                    await self._send_loop(ws)
            except Exception as e:
                self.is_connected = False
                retries += 1
                if retries == 1 or retries % 10 == 0:
                    print(f"[WebSocketClient] No backend yet — retrying silently... (attempt {retries})")
            await asyncio.sleep(self.retry_interval)

    async def _send_loop(self, ws):
        while self.is_running:
            with self.queue_lock:
                pending = self.queue.copy()
                self.queue.clear()
            for event in pending:
                try:
                    await ws.send(json.dumps(event))
                    self.sent_count += 1
                except Exception as e:
                    with self.queue_lock:
                        self.queue.insert(0, event)
                    self.failed_count += 1
                    print(f"[WebSocketClient] Send failed: {e}")
                    return
            await asyncio.sleep(0.05)

    def get_stats(self):
        return {
            "is_connected":  self.is_connected,
            "sent_count":    self.sent_count,
            "failed_count":  self.failed_count,
            "dropped_count": self.dropped_count,
            "queue_size":    len(self.queue),
            "url":           self.url,
        }
