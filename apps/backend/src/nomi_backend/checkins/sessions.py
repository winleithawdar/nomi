from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from uuid import uuid4

from sqlalchemy.orm import Session

from nomi_backend.checkins.models import CheckIn, CheckInStatus
from nomi_backend.checkins.pipeline import (
    CheckInService,
    ContactNotFound,
    send_caregiver_alert,
    send_verification_prompt,
)
from nomi_backend.checkins.semantics import LABEL_NEEDS_YOU_NOW, assess_session
from nomi_backend.checkins.wellbeing import parse_wellbeing_score
from nomi_backend.messaging.protocol import ContactRole, MessagingError
from nomi_backend.persistence.database import SessionLocal, engine
from nomi_backend.persistence.schema import (
    Base,
    CheckInMessageRecord,
    CheckInSessionRecord,
)

FOLLOW_UP_1 = (
    "How are you feeling compared with this morning — same, better, or worse?"
)
FOLLOW_UP_2 = "Is there anything you need help with today?"
THANK_YOU = "Thank you. Nomi has noted this."
MAX_SENIOR_TURNS = 3
STATUS_OPEN = "open"
STATUS_SCORED = "scored"
STATUS_MISSED = "missed"
ROLE_SENIOR = "senior"
ROLE_NOMI = "nomi"

Base.metadata.create_all(engine)

_seen_session_wamids: set[str] = set()


def handle_session_inbound(
    service: CheckInService,
    *,
    wa_id: str,
    wamid: str,
    text: str,
    db: Session | None = None,
) -> None:
    if wamid in _seen_session_wamids:
        return
    contact = service.store.get_contact_by_wa_id(wa_id)
    if contact is None or contact.role is not ContactRole.SENIOR:
        return

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        _handle_senior_message(service, db, contact.senior_id, wamid, text)
        db.commit()
        _seen_session_wamids.add(wamid)
    except Exception:
        db.rollback()
        raise
    finally:
        if close_db:
            db.close()


def record_missed_session(
    service: CheckInService,
    checkin: CheckIn,
    db: Session | None = None,
) -> None:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        existing = (
            db.query(CheckInSessionRecord)
            .filter(CheckInSessionRecord.checkin_id == checkin.id)
            .one_or_none()
        )
        now = _now(service)
        if existing is None:
            existing = CheckInSessionRecord(
                id=str(uuid4()),
                senior_id=checkin.senior_id,
                checkin_id=checkin.id,
                meal=checkin.meal,
                status=STATUS_OPEN,
                senior_turns=0,
                assessment=None,
                created_at=now,
                closed_at=None,
            )
            db.add(existing)
            db.flush()
        assessment = _score_session(service, db, existing, missed=True)
        existing.status = STATUS_MISSED
        existing.assessment = assessment.to_dict()
        existing.closed_at = now
        db.commit()
        if assessment.label == LABEL_NEEDS_YOU_NOW:
            _alert_caregiver(service, checkin.senior_id, assessment)
    except Exception:
        db.rollback()
        raise
    finally:
        if close_db:
            db.close()


def latest_scored_session_payload(senior_id: str, db: Session | None = None) -> dict | None:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        row = (
            db.query(CheckInSessionRecord)
            .filter(
                CheckInSessionRecord.senior_id == senior_id,
                CheckInSessionRecord.assessment.isnot(None),
            )
            .order_by(CheckInSessionRecord.closed_at.desc())
            .first()
        )
        if row is None:
            return None
        assessment = row.assessment or {}
        closed_at = row.closed_at
        return {
            "id": row.id,
            "meal": row.meal,
            "label": assessment.get("label"),
            "suggested_step": assessment.get("suggested_step"),
            "reasons": list(assessment.get("reasons") or []),
            "rhythm_level": assessment.get("rhythm_level"),
            "self_report_level": assessment.get("self_report_level"),
            "language_level": assessment.get("language_level"),
            "latency_minutes": assessment.get("latency_minutes"),
            "median_latency": assessment.get("median_latency"),
            "wellbeing": assessment.get("wellbeing"),
            "median_wellbeing": assessment.get("median_wellbeing"),
            "tfidf_similarity": assessment.get("tfidf_similarity"),
            "lexicon_hits": list(assessment.get("lexicon_hits") or []),
            "closed_at": closed_at.isoformat() if closed_at is not None else None,
        }
    finally:
        if close_db:
            db.close()


def _handle_senior_message(
    service: CheckInService,
    db: Session,
    senior_id: str,
    wamid: str,
    text: str,
) -> None:
    latest = service.store.latest_checkin(senior_id)
    just_closed = (
        latest is not None
        and latest.status is CheckInStatus.RESPONDED
        and latest.response_wamid == wamid
    )
    open_session = _open_session(db, senior_id)

    if just_closed:
        if open_session is not None and open_session.checkin_id == latest.id:
            return
        if open_session is not None:
            _score_and_close(service, db, open_session, missed=False)
        _start_session(service, db, latest, text)
        return

    if open_session is None:
        return

    _append_message(db, open_session, ROLE_SENIOR, text, _now(service))
    open_session.senior_turns += 1
    if open_session.senior_turns == 2:
        _send_and_store(service, db, open_session, FOLLOW_UP_2)
        return
    if open_session.senior_turns >= MAX_SENIOR_TURNS:
        _score_and_close(service, db, open_session, missed=False)
        _send_and_store(service, db, open_session, THANK_YOU)


def _start_session(
    service: CheckInService,
    db: Session,
    checkin: CheckIn,
    text: str,
) -> None:
    now = _now(service)
    row = CheckInSessionRecord(
        id=str(uuid4()),
        senior_id=checkin.senior_id,
        checkin_id=checkin.id,
        meal=checkin.meal,
        status=STATUS_OPEN,
        senior_turns=1,
        assessment=None,
        created_at=now,
        closed_at=None,
    )
    db.add(row)
    db.flush()
    _append_message(db, row, ROLE_SENIOR, text, now)
    _send_and_store(service, db, row, FOLLOW_UP_1)


def _score_and_close(
    service: CheckInService,
    db: Session,
    row: CheckInSessionRecord,
    *,
    missed: bool,
) -> None:
    assessment = _score_session(service, db, row, missed=missed)
    row.status = STATUS_MISSED if missed else STATUS_SCORED
    row.assessment = assessment.to_dict()
    row.closed_at = _now(service)
    if assessment.label == LABEL_NEEDS_YOU_NOW:
        _alert_caregiver(service, row.senior_id, assessment)


def _score_session(
    service: CheckInService,
    db: Session,
    row: CheckInSessionRecord,
    *,
    missed: bool,
):
    checkin = service.store.get_checkin(row.checkin_id) if row.checkin_id else None
    latency = None
    wellbeing = None
    if checkin is not None:
        wellbeing = checkin.wellbeing_score
        if checkin.sent_at is not None and checkin.response_received_at is not None:
            latency = (
                checkin.response_received_at - checkin.sent_at
            ).total_seconds() / 60.0

    median_latency, median_wellbeing = _personal_medians(
        service,
        row.senior_id,
        exclude_checkin_id=row.checkin_id,
    )
    session_text = " ".join(_senior_texts(db, row.id))
    if wellbeing is None:
        first = session_text.split(" ", 1)[0] if session_text.strip() else ""
        wellbeing = parse_wellbeing_score(first)
    prior_texts = _prior_session_texts(db, row.senior_id, exclude_session_id=row.id)
    return assess_session(
        latency_minutes=latency,
        median_latency=median_latency,
        wellbeing=wellbeing,
        median_wellbeing=median_wellbeing,
        session_text=session_text,
        prior_session_texts=prior_texts,
        missed=missed,
    )


def _personal_medians(
    service: CheckInService,
    senior_id: str,
    *,
    exclude_checkin_id: str | None,
) -> tuple[float | None, float | None]:
    latencies: list[float] = []
    wellbeings: list[float] = []
    for interaction in service.store.interactions_for(senior_id):
        if exclude_checkin_id and interaction.checkin_id == exclude_checkin_id:
            continue
        if interaction.response_latency_minutes is not None:
            latencies.append(interaction.response_latency_minutes)
        if interaction.wellbeing_score is not None:
            wellbeings.append(interaction.wellbeing_score)
    return (
        float(median(latencies)) if latencies else None,
        float(median(wellbeings)) if wellbeings else None,
    )


def _prior_session_texts(
    db: Session,
    senior_id: str,
    *,
    exclude_session_id: str,
) -> list[str]:
    rows = (
        db.query(CheckInSessionRecord)
        .filter(
            CheckInSessionRecord.senior_id == senior_id,
            CheckInSessionRecord.id != exclude_session_id,
            CheckInSessionRecord.assessment.isnot(None),
        )
        .all()
    )
    texts: list[str] = []
    for row in rows:
        joined = " ".join(_senior_texts(db, row.id)).strip()
        if joined:
            texts.append(joined)
    return texts


def _senior_texts(db: Session, session_id: str) -> list[str]:
    rows = (
        db.query(CheckInMessageRecord)
        .filter(
            CheckInMessageRecord.session_id == session_id,
            CheckInMessageRecord.role == ROLE_SENIOR,
        )
        .order_by(CheckInMessageRecord.created_at.asc())
        .all()
    )
    return [row.body for row in rows]


def _open_session(db: Session, senior_id: str) -> CheckInSessionRecord | None:
    return (
        db.query(CheckInSessionRecord)
        .filter(
            CheckInSessionRecord.senior_id == senior_id,
            CheckInSessionRecord.status == STATUS_OPEN,
        )
        .order_by(CheckInSessionRecord.created_at.desc())
        .first()
    )


def _append_message(
    db: Session,
    row: CheckInSessionRecord,
    role: str,
    body: str,
    created_at: datetime,
) -> None:
    db.add(
        CheckInMessageRecord(
            id=str(uuid4()),
            session_id=row.id,
            role=role,
            body=body,
            created_at=created_at,
        )
    )
    db.flush()


def _send_and_store(
    service: CheckInService,
    db: Session,
    row: CheckInSessionRecord,
    body: str,
) -> None:
    _append_message(db, row, ROLE_NOMI, body, _now(service))
    try:
        send_verification_prompt(service, row.senior_id, body)
    except (ContactNotFound, MessagingError):
        return


def _alert_caregiver(service: CheckInService, senior_id: str, assessment) -> None:
    parts = [assessment.suggested_step, *assessment.reasons]
    try:
        send_caregiver_alert(service, senior_id, " ".join(parts))
    except ContactNotFound:
        return
    except MessagingError:
        return


def _now(service: CheckInService) -> datetime:
    clock = getattr(service, "_clock", None)
    if callable(clock):
        value = clock()
        if isinstance(value, datetime):
            return value
    return datetime.now(timezone.utc)
