from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.connection_manager import manager
from routes.sessions import sessions
from models import SessionState
from scoring import compute_risk_score, classify_risk, is_banned
import json
import time

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/agent/{session_id}")
async def agent_websocket(websocket: WebSocket, session_id: str):
    """
    The candidate's browser/Electron app connects here.
    It streams events: gaze, paste, tab_switch, process, keystroke, face.
    """
    await manager.connect_agent(session_id, websocket)

    # Auto-create session if it doesn't exist yet
    if session_id not in sessions:
        sessions[session_id] = SessionState(
            session_id=session_id,
            candidate_name="Unknown"
        )

    state = sessions[session_id]

    try:
        while True:
            raw = await websocket.receive_text()

            # Safely parse incoming JSON event
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")
            event["server_timestamp"] = time.time()

            # ── Handle each event type ────────────────────────────────────────

            if event_type == "gaze":
                x, y = event.get("x", 0.5), event.get("y", 0.5)
                gaze_events = [e for e in state.events if e.get("type") == "gaze"]
                off_screen = sum(
                    1 for e in gaze_events
                    if e.get("x", 0) > 0.70 or e.get("y", 0) > 0.70
                )
                total = len(gaze_events) + 1
                # Include current event in calculation
                if x > 0.70 or y > 0.70:
                    off_screen += 1
                state.gaze_offscreen_pct = round((off_screen / total) * 100, 1)

            elif event_type == "paste":
                state.paste_count += 1

            elif event_type == "tab_switch":
                state.tab_switches += 1

            elif event_type == "keystroke":
                gap = event.get("gap_ms", 999)
                if gap < 20:  # faster than humanly possible
                    state.fast_keystroke_count += 1

            elif event_type == "process":
                name = event.get("process_name", "")
                if is_banned(name) and name not in state.banned_processes:
                    state.banned_processes.append(name)

            elif event_type == "face":
                face_count = event.get("face_count", 1)
                if face_count == 0:
                    state.no_face_count += 1
                elif face_count >= 2:
                    state.multi_face_count += 1

            # Append event to log (keep last 500 to avoid memory bloat)
            state.events.append(event)
            if len(state.events) > 500:
                state.events = state.events[-500:]

            # Recompute risk score after every event
            state.risk_score = compute_risk_score(state)
            state.risk_level = classify_risk(state.risk_score)

            # Build the payload to broadcast to all dashboards
            broadcast_payload = json.dumps({
                "session_id": session_id,
                "candidate_name": state.candidate_name,
                "risk_score": state.risk_score,
                "risk_level": state.risk_level,
                "gaze_offscreen_pct": state.gaze_offscreen_pct,
                "paste_count": state.paste_count,
                "tab_switches": state.tab_switches,
                "fast_keystroke_count": state.fast_keystroke_count,
                "no_face_count": state.no_face_count,
                "multi_face_count": state.multi_face_count,
                "banned_processes": state.banned_processes,
                "latest_event": event,
            })

            await manager.broadcast_to_dashboards(broadcast_payload)

    except WebSocketDisconnect:
        manager.disconnect_agent(session_id)


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """
    The interviewer's dashboard connects here.
    It receives live broadcasts whenever any candidate's state updates.
    """
    await manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping from client
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)