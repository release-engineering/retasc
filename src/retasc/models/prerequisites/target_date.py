# SPDX-License-Identifier: GPL-3.0-or-later
from textwrap import dedent

from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteTargetDate(PrerequisiteBase):
    """
    Prerequisite target start date.

    The prerequisite state is Completed only if the target_date evaluates to a
    date in the past or it is today. Otherwise, the state is Pending.

    Additionally, if ignore_drafts is true (the default value), the
    prerequisite state is always Pending if the scheduled item is draft (i.e.
    schedule_task_is_draft template parameter is true).

    Adds the following template parameters:
    - target_date - the evaluated target date
    """

    target_date: str = Field(
        description=dedent("""
            Expression that evaluates to a target date indicating the earliest
            possible start. Examples:
            - "start_date - 3|weeks"
            - "end_date + 1|days"
            - "today"
        """).strip(),
    )
    ignore_drafts: bool = Field(
        description="Ignore draft scheduled items if true (the default).", default=True
    )

    def update_state(self, context) -> ReleaseRuleState:
        """
        Return Completed if target date is earlier than today,
        otherwise return Pending.
        """
        if self.ignore_drafts and context.template.params["schedule_task_is_draft"]:
            context.report.set("schedule_task_is_draft", True)
            return ReleaseRuleState.Pending

        target_date = context.template.evaluate(self.target_date)
        context.template.params["target_date"] = target_date
        today = context.template.env.globals["today"]
        days_remaining = (target_date - today).days
        context.report.set("target_date", target_date)
        if days_remaining > 0:
            context.report.set("days_remaining", days_remaining)
            return ReleaseRuleState.Pending
        return ReleaseRuleState.Completed

    def section_name(self, context) -> str:
        return f"TargetDate({self.target_date!r})"
