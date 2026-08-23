"""
Daily streak tracking -- Beli/Duolingo-style gamification (item #4 of the
agreed roadmap). What counts as a "streak day" is deliberately left
undecided by product for now (the user's own words: "not sure just yet"),
so record_activity() below is called on every app open -- the loosest,
easiest-to-swap-later definition ("just opening the app" keeps the
streak alive) rather than gating it on ranking a place. Swapping to a
stricter trigger later only means changing *where* record_activity() is
called from, not this file.

Duolingo's own documented pattern, confirmed via research and followed
here:
- The server is the source of truth for "now" (never the device clock).
- Streak continuity is judged by calendar day, not by hours-since-last-
  activity -- comparing raw elapsed time is the most common place this
  gets built wrong (someone active at 11pm and again at 1am is two
  different calendar days but under 3 hours apart; someone active at
  6am and again at 11pm the same day is 17 hours apart but one day).
- "Calendar day" only means something relative to a timezone. The
  client supplies its current IANA timezone name (validated against the
  real zoneinfo database, falling back to UTC on anything unrecognized)
  so the day boundary lines up with where the user actually is, while
  the instant itself (datetime.now(UTC)) still only ever comes from the
  server.

No "streak freeze" concept yet (Duolingo's grace mechanic for a missed
day) -- out of scope for this pass; a missed day currently just resets
current_streak to 1 on the next activity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.db.models.user_streak import UserStreak

_DEFAULT_TZ = "UTC"


@dataclass
class StreakState:
    current_streak: int
    longest_streak: int
    last_active_date: date | None


def _local_today(client_timezone: str | None) -> date:
    now_utc = datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(client_timezone) if client_timezone else ZoneInfo(_DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        tz = ZoneInfo(_DEFAULT_TZ)
    return now_utc.astimezone(tz).date()


def get_streak(db: Session, *, user_id: str) -> StreakState:
    streak = db.query(UserStreak).filter(UserStreak.user_id == user_id).one_or_none()
    if streak is None:
        return StreakState(current_streak=0, longest_streak=0, last_active_date=None)
    return StreakState(
        current_streak=streak.current_streak,
        longest_streak=streak.longest_streak,
        last_active_date=streak.last_active_date,
    )


def record_activity(db: Session, *, user_id: str, client_timezone: str | None) -> StreakState:
    today = _local_today(client_timezone)
    streak = db.query(UserStreak).filter(UserStreak.user_id == user_id).one_or_none()

    if streak is None:
        streak = UserStreak(
            user_id=user_id,
            current_streak=1,
            longest_streak=1,
            last_active_date=today,
        )
        db.add(streak)
        db.commit()
        return get_streak(db, user_id=user_id)

    if streak.last_active_date is None:
        streak.current_streak = 1
        streak.longest_streak = max(streak.longest_streak, 1)
        streak.last_active_date = today
        db.commit()
        return get_streak(db, user_id=user_id)

    gap_days = (today - streak.last_active_date).days

    if gap_days == 0:
        # Already recorded today (e.g. app opened twice) -- no-op.
        pass
    elif gap_days == 1:
        streak.current_streak += 1
        streak.longest_streak = max(streak.longest_streak, streak.current_streak)
        streak.last_active_date = today
    elif gap_days > 1:
        streak.current_streak = 1
        streak.longest_streak = max(streak.longest_streak, 1)
        streak.last_active_date = today
    else:
        # gap_days < 0 -- "today" computed as earlier than the stored
        # last_active_date (e.g. a client reporting an implausible
        # timezone). Never move the streak backward or let this be used
        # to replay activity into the past; leave the stored state alone.
        pass

    db.commit()
    return get_streak(db, user_id=user_id)
