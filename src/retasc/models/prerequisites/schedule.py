# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import UTC, datetime, timedelta
from functools import cache

from pydantic import BaseModel, Field

from retasc.models.release_rule_state import ReleaseRuleState


@cache
def today():
    return datetime.now(UTC).date()


class PrerequisiteSchedule(BaseModel):
    """Prerequisite Product Pages schedule."""

    schedule_task: str = Field(
        description="The name of the Product Pages schedule item."
    )
    days_before_or_after: int = Field(
        description=(
            "The number of days to adjust the schedule relative to the PP schedule item date. "
            "A negative value indicates the number of days before the PP schedule item date, "
            "while a positive value indicates the number of days after the PP schedule item date. "
            "This value helps determine the target date for creating Jira issues."
        ),
    )

    def state(self, *, context, release, **_kwargs) -> ReleaseRuleState:
        schedule = context.pp.release_schedule(context.release)
        start_date = schedule[self.schedule_task]
        if today() >= start_date + timedelta(self.days_before_or_after):
            return ReleaseRuleState.Completed
        return ReleaseRuleState.Pending
