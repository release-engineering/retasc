# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteRule(PrerequisiteBase):
    """
    Reference to other required rule.

    The prerequisite state is based on the referenced rule
    prerequisites:
    - Pending, if some prerequisites are in Pending
    - In-progress, if some prerequisites are in In-progress but none are Pending
    - Completed, if all prerequisites are Completed
    """

    rule: str = Field(description="Name of the required rule")

    def validation_errors(self, rules, config) -> list[str]:
        if not any(self.rule == rule.name for rule in rules):
            return [f"Dependent rule does not exist: {self.rule!r}"]
        return []

    def update_state(self, context) -> ReleaseRuleState:
        """Return Completed only if all rules were closed."""
        rule = context.template.render(self.rule)
        return context.rules[rule].update_state(context)

    def section_name(self, context) -> str:
        return f"Rule({self.rule!r})"
