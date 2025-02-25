# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteSchedule(PrerequisiteBase):
    """
    Prerequisite Product Pages schedule.

    The schedule must exist, otherwise an error is raised.

    The prerequisite state is always Completed.

    Adds the following template parameters:
    - schedule - dict with all schedules for the current release
    - schedule_task - name of the schedule task
    - start_date - the schedule task's start_date
    - end_date - the schedule task's end_date
    - schedule_task_is_draft - if schedule task is marked as draft
    """

    schedule_task: str = Field(
        description="The name of the Product Pages schedule item."
    )

    def _params(self, schedule: dict, context) -> dict:
        local_params = {"schedule": schedule}
        schedule_task = context.template.render(self.schedule_task, **local_params)
        # Some old releases may not have newer milestone
        if schedule_task not in schedule:
            return {}
        task = schedule[schedule_task]
        local_params.update(
            {
                "schedule_task": schedule_task,
                "start_date": task.start_date,
                "end_date": task.end_date,
                "schedule_task_is_draft": task.is_draft,
            }
        )
        return local_params

    def update_state(self, context) -> ReleaseRuleState:
        """
        Fetch schedule and given task, update templating parameters and
        return Completed.

        Raises a HTTPError if the schedule task does not exist.
        """
        release = context.template.params["release"]
        schedule = context.pp.release_schedules(release)
        if schedule == {}:
            context.report.set("pending_reason", "No schedule available yet")
            return ReleaseRuleState.Pending

        local_params = self._params(schedule, context)
        if local_params == {}:
            context.report.set("skip_reason", "No rule's task set in the schedule yet")
            return ReleaseRuleState.Skip
        context.template.params.update(local_params)
        return ReleaseRuleState.Completed

    def section_name(self, context) -> str:
        return f"Schedule({self.schedule_task!r})"
