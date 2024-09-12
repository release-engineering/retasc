# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteSchedule(PrerequisiteBase):
    """
    Prerequisite Product Pages schedule.

    Adds the following template parameters:
    - schedule - dict with all schedules for the current release
    - schedule_task - name of the schedule task
    - start_date - the schedule task's start_date
    - end_date - the schedule task's start_date
    """

    schedule_task: str = Field(
        description="The name of the Product Pages schedule item."
    )

    def _params(self, context) -> dict:
        schedule = context.pp.release_schedules(context.release)
        local_params = {"schedule": schedule}

        schedule_task = context.template.render(self.schedule_task, **local_params)
        task = schedule[schedule_task]
        local_params.update(
            {
                "schedule_task": schedule_task,
                "start_date": task.start_date,
                "end_date": task.end_date,
            }
        )
        return local_params

    def update_state(self, context) -> ReleaseRuleState:
        """
        Fetch schedule and given task, update templating parameters and
        return Completed.

        Raises a HTTPError if the schedule task does not exist.
        """
        local_params = self._params(context)
        context.template.params.update(local_params)
        return ReleaseRuleState.Completed

    def section_name(self) -> str:
        return f"Schedule({self.schedule_task!r})"
