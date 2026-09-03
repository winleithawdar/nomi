from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from nomi_backend.checkins.pipeline import CheckInService, ContactNotFound
from nomi_backend.checkins.store import CheckInStore
from nomi_backend.messaging.protocol import MessagingError

TIMEZONE_NAME = "Asia/Singapore"
SGT = ZoneInfo(TIMEZONE_NAME)

MEAL_BREAKFAST = "breakfast"
MEAL_LUNCH = "lunch"
MEAL_DINNER = "dinner"

MEAL_STARTS = {
    MEAL_BREAKFAST: time(8, 0),
    MEAL_LUNCH: time(12, 30),
    MEAL_DINNER: time(18, 30),
}


def to_sgt(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(SGT)


def current_meal(now: datetime) -> str | None:
    local_time = to_sgt(now).time()
    if local_time >= MEAL_STARTS[MEAL_DINNER]:
        return MEAL_DINNER
    if local_time >= MEAL_STARTS[MEAL_LUNCH]:
        return MEAL_LUNCH
    if local_time >= MEAL_STARTS[MEAL_BREAKFAST]:
        return MEAL_BREAKFAST
    return None


def next_meal(now: datetime) -> tuple[str, datetime]:
    local = to_sgt(now)
    local_time = local.time()
    day = local.date()
    if local_time < MEAL_STARTS[MEAL_BREAKFAST]:
        meal = MEAL_BREAKFAST
    elif local_time < MEAL_STARTS[MEAL_LUNCH]:
        meal = MEAL_LUNCH
    elif local_time < MEAL_STARTS[MEAL_DINNER]:
        meal = MEAL_DINNER
    else:
        meal = MEAL_BREAKFAST
        day = day + timedelta(days=1)
    when = datetime.combine(day, MEAL_STARTS[meal], tzinfo=SGT)
    return meal, when


def meal_window(meal: str, now: datetime) -> tuple[datetime, datetime]:
    local = to_sgt(now)
    day = local.date()
    if meal == MEAL_BREAKFAST:
        start = datetime.combine(day, MEAL_STARTS[MEAL_BREAKFAST], tzinfo=SGT)
        end = datetime.combine(day, MEAL_STARTS[MEAL_LUNCH], tzinfo=SGT)
        return start, end
    if meal == MEAL_LUNCH:
        start = datetime.combine(day, MEAL_STARTS[MEAL_LUNCH], tzinfo=SGT)
        end = datetime.combine(day, MEAL_STARTS[MEAL_DINNER], tzinfo=SGT)
        return start, end
    if local.time() < MEAL_STARTS[MEAL_BREAKFAST]:
        start = datetime.combine(day - timedelta(days=1), MEAL_STARTS[MEAL_DINNER], tzinfo=SGT)
        end = datetime.combine(day, MEAL_STARTS[MEAL_BREAKFAST], tzinfo=SGT)
        return start, end
    start = datetime.combine(day, MEAL_STARTS[MEAL_DINNER], tzinfo=SGT)
    end = datetime.combine(day + timedelta(days=1), MEAL_STARTS[MEAL_BREAKFAST], tzinfo=SGT)
    return start, end


def already_sent_this_meal(
    store: CheckInStore,
    senior_id: str,
    meal: str,
    now: datetime,
) -> bool:
    start, end = meal_window(meal, now)
    for checkin in store.list_checkins(senior_id):
        sent_at = checkin.sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        sent_local = sent_at.astimezone(SGT)
        if start <= sent_local < end:
            return True
    return False


def run_due(store: CheckInStore, service: CheckInService, now: datetime) -> list[str]:
    meal = current_meal(now)
    if meal is None:
        return []

    sent: list[str] = []
    for senior_id in store.list_senior_ids():
        try:
            _send_if_due(store, service, senior_id, meal, now, sent)
        except (ContactNotFound, MessagingError):
            continue
        except Exception:
            continue
    return sent


def _send_if_due(
    store: CheckInStore,
    service: CheckInService,
    senior_id: str,
    meal: str,
    now: datetime,
    sent: list[str],
) -> None:
    open_checkin = store.get_open_checkin(senior_id)
    if open_checkin is not None:
        if already_sent_this_meal(store, senior_id, meal, now):
            return
        missed = service.mark_missed(open_checkin.id, as_of=now)
        try:
            from nomi_backend.checkins.sessions import record_missed_session

            record_missed_session(service, store.get_checkin(open_checkin.id) or open_checkin)
        except Exception:
            pass
        _ = missed

    if already_sent_this_meal(store, senior_id, meal, now):
        return

    service.send_checkin(senior_id, meal=meal)
    sent.append(senior_id)
