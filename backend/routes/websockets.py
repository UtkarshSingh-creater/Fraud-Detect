from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from core.connection_manager import manager
from routes.sessions import sessions
from models import SessionState
from scoring import compute_risk_score, classify_risk, is_banned
import json
import time

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/agent/{session_id}")
async def agent_websocket(
    websocket: WebSocket,
    session_id: str,
    api_key: str = Query(...),   # FIX: require api_key query param
):
    # FIX: verify api_key before accepting
    from core.config import AGENT_API_KEY
    if api_key != AGENT_API_KEY:
        await websocket.close(code=4403, reason="Invalid agent API key")
        return

    await websocket.accept()
    await manager.connect_agent(session_id, websocket)

    if session_id not in sessions:
        sessions[session_id] = SessionState(
            session_id=session_id,
            candidate_name="Unknown"
        )

    state = sessions[session_id]

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")
            event["server_timestamp"] = time.time()

            # ── Core events ───────────────────────────────────────────────────

            if event_type == "gaze":
                x, y = event.get("x", 0.5), event.get("y", 0.5)
                gaze_events = [e for e in state.events if e.get("type") == "gaze"]
                off = sum(1 for e in gaze_events if e.get("x", 0) > 0.70 or e.get("y", 0) > 0.70)
                total = len(gaze_events) + 1
                if x > 0.70 or y > 0.70:
                    off += 1
                state.gaze_offscreen_pct = round((off / total) * 100, 1)

            elif event_type == "paste":
                state.paste_count += 1

            elif event_type == "tab_switch":
                state.tab_switches += 1

            elif event_type == "keystroke":
                gap = event.get("gap_ms", 999)
                if gap < 20:
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

            # ── FIX: ML model event types — were missing, all events dropped ──

            elif event_type == "audio":
                if event.get("multiple_speakers") or event.get("whisper_detected"):
                    state.multi_face_count += 1   # audio anomaly tracked here

            elif event_type == "liveness":
                if event.get("flagged"):
                    state.no_face_count += 1

            elif event_type == "deepfake":
                if event.get("is_synthetic") or event.get("flagged"):
                    name = "deepfake_detected"
                    if name not in state.banned_processes:
                        state.banned_processes.append(name)

            elif event_type == "head_pose":
                if event.get("flagged"):
                    state.fast_keystroke_count += 1

            elif event_type in ("mouse_move", "keystroke_anomaly",
                                "face_verify", "face_missing",
                                "multiple_faces", "tab_switch",
                                "biometric_anomaly", "temporal_pattern",
                                "banned_object", "heartbeat"):
                pass   # logged only — no state mutation needed

            # Keep rolling log capped at 500
            state.events.append(event)
            if len(state.events) > 500:
                state.events = state.events[-500:]

            # Recompute risk
            state.risk_score = compute_risk_score(state)
            state.risk_level = classify_risk(state.risk_score)

            await manager.broadcast_to_dashboards(json.dumps({
                "session_id":           session_id,
                "candidate_name":       state.candidate_name,
                "risk_score":           state.risk_score,
                "risk_level":           state.risk_level,
                "gaze_offscreen_pct":   state.gaze_offscreen_pct,
                "paste_count":          state.paste_count,
                "tab_switches":         state.tab_switches,
                "fast_keystroke_count": state.fast_keystroke_count,
                "no_face_count":        state.no_face_count,
                "multi_face_count":     state.multi_face_count,
                "banned_processes":     state.banned_processes,
                "latest_event":         event,
            }))

    except WebSocketDisconnect:
        manager.disconnect_agent(session_id)


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
