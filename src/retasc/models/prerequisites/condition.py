# SPDX-License-Identifier: GPL-3.0-or-later
from textwrap import dedent

from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteCondition(PrerequisiteBase):
    """
    Custom condition evaluated by templating engine.

    The prerequisite state is Completed only if the evaluated value is true,
    otherwise it is Pending.
    """

    condition: str = Field(
        description=dedent("""
            Conditional expression. Examples:
            - "major >= 10"
            - "today.weekday() < SATURDAY"
        """).strip()
    )

    def update_state(self, context) -> ReleaseRuleState:
        is_completed = context.template.evaluate(self.condition)
        context.report.set("result", is_completed)
        return ReleaseRuleState.Completed if is_completed else ReleaseRuleState.Pending

    def section_name(self) -> str:
        return f"Condition({self.condition!r})"
