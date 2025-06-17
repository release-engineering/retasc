# SPDX-License-Identifier: GPL-3.0-or-later
import re
from textwrap import dedent

from pydantic import Field

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.utils import to_comma_separated

from .base import PrerequisiteBase


def to_regex(re_string: str) -> re.Pattern | None:
    """
    If re_string is enclosed in slashes, return regular expression, otherwise
    returns None.

    Throws an PrerequisiteUpdateStateError if regular expression pattern is
    invalid or the re_string only starts or ends with slash.
    """
    slash_start = re_string.startswith("/")
    slash_end = re_string.endswith("/")
    if slash_start != slash_end:
        raise PrerequisiteUpdateStateError(
            f"Regular expression string {re_string!r} must be enclosed with"
            " slash character '/' on both sides."
        )

    if not slash_start:
        return None

    pattern = re_string[1:-1]
    try:
        return re.compile(pattern)
    except re.PatternError as e:
        raise PrerequisiteUpdateStateError(
            f"Invalid regular expression pattern {pattern!r}: {e}"
        )


class PrerequisiteSchedule(PrerequisiteBase):
    """
    Prerequisite Product Pages schedule.

    If schedule does not contain any tasks yet, the state would be Pending.

    If schedule contains tasks and skip_if_missing is False, a unique matching
    schedule must exist, otherwise an error is raised.

    The prerequisite state is Completed if the schedule task is found.

    Adds the following template parameters:
    - schedule - dict with all schedules for the current release
    - schedule_task - name of the matching schedule task
    - start_date - the schedule task's start_date
    - end_date - the schedule task's end_date
    - schedule_task_is_draft - if schedule task is marked as draft
    """

    schedule_task: str = Field(
        description=dedent("""
            The name of the Product Pages schedule task or a regular expression
            pattern enclosed in slashes (/) to match a full task name.

            This is first evaluated by templating engine.

            Examples:
            - "New release"
            - "New configuration for RHEL {{ major }}.{{ minor }}"
            - "/Setup release config.*/"
            - "{{ '/Setup release config.*/' if major > 2 else 'New Release Config' }}"
        """).strip()
    )
    skip_if_missing: bool = Field(
        default=False,
        description=dedent("""
            If True, the prerequisite will not raise an error if the schedule
            task is not found, but will set the state to Pending instead.
        """).strip(),
    )

    def _params(self, schedule: list, context) -> dict:
        local_params = {"schedule": schedule}
        schedule_task = context.template.render(self.schedule_task, **local_params)
        schedule_task_re = to_regex(schedule_task)
        if schedule_task_re:
            tasks = [task for task in schedule if schedule_task_re.fullmatch(task.name)]
        else:
            tasks = [task for task in schedule if task.name == schedule_task]

        if not tasks:
            if self.skip_if_missing:
                return {}
            raise PrerequisiteUpdateStateError(
                f"Failed to find schedule task with name {schedule_task!r}"
            )

        if len(tasks) > 1:
            if schedule_task_re:
                task_names = to_comma_separated(task.name for task in tasks)
                raise PrerequisiteUpdateStateError(
                    f"Found multiple schedule tasks matching {repr(schedule_task)[1:-1]}"
                    f", matching are: {task_names}"
                )
            else:
                raise PrerequisiteUpdateStateError(
                    f"Found multiple schedule tasks with name {schedule_task!r}"
                )

        task = tasks[0]
        local_params.update(
            {
                "schedule_task": task.name,
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
        if schedule == []:
            context.report.set("schedule_task", self.schedule_task)
            context.report.set("pending_reason", "No schedule available yet")
            return ReleaseRuleState.Pending

        local_params = self._params(schedule, context)
        if not local_params:
            return ReleaseRuleState.Pending

        context.report.set("schedule_task", local_params["schedule_task"])
        context.template.params.update(local_params)
        return ReleaseRuleState.Completed
