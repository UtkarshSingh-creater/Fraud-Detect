from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from db_models import DBSession, DBEvent
from models import SessionState
import time


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(db: AsyncSession, session_id: str, candidate_name: str) -> DBSession:
    row = DBSession(session_id=session_id, candidate_name=candidate_name)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_session(db: AsyncSession, session_id: str) -> DBSession | None:
    result = await db.execute(
        select(DBSession).where(DBSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(db: AsyncSession, active_only: bool = False) -> list[DBSession]:
    q = select(DBSession)
    if active_only:
        q = q.where(DBSession.is_active == True)
    result = await db.execute(q.order_by(DBSession.created_at.desc()))
    return list(result.scalars().all())


async def update_session_state(db: AsyncSession, state: SessionState):
    """Sync in-memory SessionState into the DB after every event."""
    await db.execute(
        update(DBSession)
        .where(DBSession.session_id == state.session_id)
        .values(
            risk_score=state.risk_score,
            risk_level=state.risk_level,
            gaze_offscreen_pct=state.gaze_offscreen_pct,
            paste_count=state.paste_count,
            tab_switches=state.tab_switches,
            fast_keystroke_count=state.fast_keystroke_count,
            no_face_count=state.no_face_count,
            multi_face_count=state.multi_face_count,
            banned_processes=state.banned_processes,
        )
    )
    await db.commit()


async def deactivate_session(db: AsyncSession, session_id: str):
    """Mark session as ended rather than deleting it (preserves history)."""
    await db.execute(
        update(DBSession)
        .where(DBSession.session_id == session_id)
        .values(is_active=False)
    )
    await db.commit()


# ── Events ────────────────────────────────────────────────────────────────────

async def save_event(db: AsyncSession, session_id: str, event: dict):
    row = DBEvent(
        session_id=session_id,
        event_type=event.get("type", "unknown"),
        payload=event,
        server_timestamp=event.get("server_timestamp", time.time()),
    )
    db.add(row)
    await db.commit()


async def get_events(db: AsyncSession, session_id: str) -> list[DBEvent]:
    result = await db.execute(
        select(DBEvent)
        .where(DBEvent.session_id == session_id)
        .order_by(DBEvent.server_timestamp.asc())
    )
    return list(result.scalars().all())


# ── Export helpers ────────────────────────────────────────────────────────────

async def get_session_with_events(db: AsyncSession, session_id: str):
    """Return session row + all events — used by the export endpoints."""
    session = await get_session(db, session_id)
    if not session:
        return None, []
    events = await get_events(db, session_id)
    return session, events