# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState
from retasc.utils import to_comma_separated

from .base import PrerequisiteBase


class PrerequisiteRule(PrerequisiteBase):
    """Prerequisite Rule."""

    rules: list[str] = Field(
        default=[],
        description="The prerequisite rule",
    )

    def validation_errors(self, rules) -> list[str]:
        missing_rules = [
            name for name in self.rules if not any(name == rule.name for rule in rules)
        ]
        if missing_rules:
            rules_list = to_comma_separated(missing_rules)
            return [f"Dependent rules do not exist: {rules_list}"]
        return []

    def state(self, *, context, release) -> ReleaseRuleState:
        """Returns Completed only if all rules were closed."""
        return min(
            context.rules[name].state(context=context, release=release)
            for name in self.rules
        )
