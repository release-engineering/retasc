# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import Field

from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteVariableString(PrerequisiteBase):
    """Set templating string variable."""

    variable: str = Field(description="Variable name")
    string: str = Field(description="Variable value - a string template")

    def update_state(self, context) -> ReleaseRuleState:
        value = context.template.render(self.string)
        context.report.set("value", value)
        context.template.params[self.variable] = value
        return ReleaseRuleState.Completed

    def section_name(self, context) -> str:
        return f"VariableString({self.variable!r})"
