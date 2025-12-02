# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import UTC, date, datetime, timedelta

from jinja2 import Environment


def today():
    return datetime.now(UTC).date()


def now():
    return datetime.now(UTC)


def days(value: int) -> timedelta:
    return timedelta(days=value)


def weeks(value: int) -> timedelta:
    return timedelta(weeks=value)


def hours(value: int) -> timedelta:
    return timedelta(hours=value)


def minutes(value: int) -> timedelta:
    return timedelta(minutes=value)


def seconds(value: int) -> timedelta:
    return timedelta(seconds=value)


def to_date(value: str) -> date:
    """
    Parse a date string in the format YYYY-MM-DD.
    """
    return datetime.strptime(value, "%Y-%m-%d").date()


GLOBALS = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
    "date": to_date,
    "now": now,
    "datetime": datetime,
}
FILTERS = {
    "days": days,
    "weeks": weeks,
    "hours": hours,
    "minutes": minutes,
    "seconds": seconds,
    "day": days,
    "week": weeks,
    "hour": hours,
    "minute": minutes,
    "second": seconds,
    "date": to_date,
}


def update_environment(env: Environment):
    env.filters.update(FILTERS)
    env.globals.update(FILTERS)
    env.globals.update(GLOBALS)
    env.globals["today"] = today()
