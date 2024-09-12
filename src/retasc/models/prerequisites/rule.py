# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteRule(PrerequisiteBase):
    """Prerequisite Rule."""

    rule: str = Field(description="The prerequisite rule")

    def validation_errors(self, rules) -> list[str]:
        if not any(self.rule == rule.name for rule in rules):
            return [f"Dependent rule does not exist: {self.rule!r}"]
        return []

    def update_state(self, context) -> ReleaseRuleState:
        """Return Completed only if all rules were closed."""
        rule = context.template.render(self.rule)
        return context.rules[rule].update_state(context=context)

    def section_name(self) -> str:
        return f"Rule({self.rule!r})"
