from fastapi import WebSocket


class ConnectionManager:
    """
    Manages all active WebSocket connections.
    
    - agent_clients   : one connection per candidate (keyed by session_id)
    - dashboard_clients : all interviewer dashboards listening for updates
    """

    def __init__(self):
        '''self.agent_clients: dict[str, WebSocket] = {}
        self.dashboard_clients: list[WebSocket] = []'''
        self.agent_connections:     dict[str, WebSocket] = {}   # session_id → websocket
        self.dashboard_connections: list[WebSocket]      = []   # all interviewer dashboards

    # ── Agent (candidate) connections ─────────────────────────────────────────

    async def connect_agent(self, session_id: str, websocket: WebSocket):
        #await websocket.accept()
        self.agent_connections[session_id] = websocket

    def disconnect_agent(self, session_id: str):
        self.agent_connections.pop(session_id, None)

    def get_agent(self, session_id: str) -> WebSocket | None:
        return self.agent_connections.get(session_id)

    # ── Dashboard (interviewer) connections ───────────────────────────────────

    async def connect_dashboard(self, websocket: WebSocket):
        #await websocket.accept()
        self.dashboard_clients.append(websocket)

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.dashboard_clients:
            self.dashboard_clients.remove(websocket)

    # ── Broadcast to all dashboards ───────────────────────────────────────────

    async def broadcast_to_dashboards(self, message: str):
        """Send a JSON string to every connected interviewer dashboard."""
        dead_clients = []
        for client in self.dashboard_clients:
            try:
                await client.send_text(message)
            except Exception:
                dead_clients.append(client)
        # Clean up disconnected clients
        for dead in dead_clients:
            self.dashboard_clients.remove(dead)
            
    
    async def send_to_agent(self, session_id: str, message: str) -> bool:
        """
        Send a message directly to a specific candidate agent.
        Returns True if sent, False if agent not connected.
        (Reserved for future use — e.g. interviewer sending a warning to candidate.)
        """
        ws = self.agent_connections.get(session_id)
        if not ws:
            return False
        try:
            await ws.send_text(message)
            return True
        except Exception:
            self.disconnect_agent(session_id)
            return False


# Single shared instance used across the whole app
manager = ConnectionManager()