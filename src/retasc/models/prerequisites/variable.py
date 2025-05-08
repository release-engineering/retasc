# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteVariable(PrerequisiteBase):
    """Set templating variable value."""

    variable: str = Field(description="Variable name")
    value: str = Field(
        description="Variable value - an expression to evaluate by the templating engine"
    )

    def update_state(self, context) -> ReleaseRuleState:
        context.report.set("variable", self.variable)
        value = context.template.evaluate(self.value)
        context.report.set("value", value)
        context.template.params[self.variable] = value
        return ReleaseRuleState.Completed
