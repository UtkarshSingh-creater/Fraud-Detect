import csv
import json
import io
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from crud import get_session_with_events
from core.auth import get_current_interviewer

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/{session_id}/json")
async def export_json(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_interviewer),
):
    """Download full session + all events as a JSON file."""
    session, events = await get_session_with_events(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    payload = {
        "session": {
            "session_id":          session.session_id,
            "candidate_name":      session.candidate_name,
            "risk_score":          session.risk_score,
            "risk_level":          session.risk_level,
            "gaze_offscreen_pct":  session.gaze_offscreen_pct,
            "paste_count":         session.paste_count,
            "tab_switches":        session.tab_switches,
            "fast_keystroke_count": session.fast_keystroke_count,
            "no_face_count":       session.no_face_count,
            "multi_face_count":    session.multi_face_count,
            "banned_processes":    session.banned_processes,
            "is_active":           session.is_active,
            "created_at":          str(session.created_at),
            "updated_at":          str(session.updated_at),
        },
        "events": [
            {
                "id":               e.id,
                "event_type":       e.event_type,
                "server_timestamp": e.server_timestamp,
                **e.payload,
            }
            for e in events
        ],
    }

    content = json.dumps(payload, indent=2)
    return StreamingResponse(
        io.StringIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.json"},
    )


@router.get("/{session_id}/csv")
async def export_csv(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_interviewer),
):
    """Download all events for a session as a CSV file."""
    session, events = await get_session_with_events(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "event_id", "session_id", "candidate_name",
        "event_type", "server_timestamp", "payload_json"
    ])

    for e in events:
        writer.writerow([
            e.id,
            session_id,
            session.candidate_name,
            e.event_type,
            e.server_timestamp,
            json.dumps(e.payload),
        ])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"},
    )