# SPDX-License-Identifier: GPL-3.0-or-later
import re
from textwrap import dedent
from typing import Self

from pydantic import Field, model_validator

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.utils import to_comma_separated

from .base import PrerequisiteBase


def to_regex(re_string: str) -> re.Pattern:
    """
    If re_string is enclosed in slashes, return regular expression with
    re_string pattern, otherwise returns regular expression matching just the
    re_string.

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
        return re.compile(re.escape(re_string))

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
    - schedule_slug - name of the matching schedule task
    - start_date - the schedule task's start_date
    - end_date - the schedule task's end_date
    - schedule_task_is_draft - if schedule task is marked as draft
    """

    schedule_task: str | None = Field(
        description=dedent("""
            The name of the Product Pages schedule task or a regular expression
            pattern enclosed in slashes (/) to match a full task name.

            This is first evaluated by templating engine.

            Examples:
            - "New release"
            - "New configuration for RHEL {{ major }}.{{ minor }}"
            - "/Setup release config.*/"
            - "{{ '/Setup release config.*/' if major > 2 else 'New Release Config' }}"
        """).strip(),
        default=None,
    )
    schedule_slug: str | None = Field(
        description=dedent("""
            The slug value of the Product Pages schedule task or a regular expression
            pattern enclosed in slashes (/) to match a full task name.

            This is first evaluated by templating engine.
        """).strip(),
        default=None,
    )
    skip_if_missing: bool = Field(
        default=False,
        description=dedent("""
            If True, the prerequisite will not raise an error if the schedule
            task is not found, but will set the state to Pending instead.
        """).strip(),
    )

    @model_validator(mode="after")
    def check_task_or_slug_is_set(self) -> Self:
        if self.schedule_task is None and self.schedule_slug is None:
            raise ValueError("Either schedule_task or schedule_slug must be set")
        return self

    def _filter_tasks(
        self, tasks: list, attribute_to_match: str, query: str | None, context
    ) -> list:
        if query is None:
            return tasks

        pattern = context.template.render(query, schedule=tasks)
        regex = to_regex(pattern)
        tasks = [
            task for task in tasks if regex.fullmatch(getattr(task, attribute_to_match))
        ]

        if not tasks:
            if self.skip_if_missing:
                return []
            raise PrerequisiteUpdateStateError(
                f"Failed to find schedule task matching {attribute_to_match} {pattern!r}"
            )

        if len(tasks) > 1:
            task_values = to_comma_separated(
                getattr(task, attribute_to_match) for task in tasks
            )
            raise PrerequisiteUpdateStateError(
                f"Found multiple schedule tasks matching {attribute_to_match} {pattern!r}"
                f", matching are: {task_values}"
            )

        return tasks

    def _params(self, schedule: list, context) -> dict:
        tasks = schedule
        tasks = self._filter_tasks(tasks, "name", self.schedule_task, context)
        tasks = self._filter_tasks(tasks, "slug", self.schedule_slug, context)
        if not tasks:
            return {}

        task = tasks[0]
        return {
            "schedule": schedule,
            "schedule_task": task.name,
            "schedule_slug": task.slug,
            "start_date": task.start_date,
            "end_date": task.end_date,
            "schedule_task_is_draft": task.is_draft,
        }

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
