# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import UTC, datetime, timedelta
from functools import cache

from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


@cache
def today():
    return datetime.now(UTC).date()


class PrerequisiteSchedule(PrerequisiteBase):
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

    def state(self, context) -> ReleaseRuleState:
        """Returns Completed only if the scheduled date is in past."""
        schedule = context.pp.release_schedules(context.release)
        task_name = context.template.render(self.schedule_task)
        task = schedule[task_name]
        start_date = task.start_date
        if today() >= start_date + timedelta(self.days_before_or_after):
            return ReleaseRuleState.Completed
        return ReleaseRuleState.Pending

    def update_params(self, params: dict, context):
        schedule = context.pp.release_schedules(context.release)
        task_name = context.template.render(self.schedule_task)
        task = schedule[task_name]

        # set minimum start_date and maximum end_date
        start_date = params.get("start_date")
        task_start_date = task.start_date + timedelta(self.days_before_or_after)
        if start_date:
            new_start_date = min(start_date, task_start_date)
        else:
            new_start_date = task_start_date

        end_date = params.get("end_date")
        if end_date:
            new_end_date = max(end_date, task.end_date)
        else:
            new_end_date = task.end_date

        params["start_date"] = new_start_date
        params["end_date"] = max(new_start_date, new_end_date)

        params["schedule"] = schedule
        params["schedule_task_name"] = task_name
        params["schedule_task"] = task
        params["days_before_or_after"] = self.days_before_or_after
