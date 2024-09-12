# SPDX-License-Identifier: GPL-3.0-or-later
from functools import cache

from pydantic import BaseModel, Field

from retasc.models.prerequisites import Prerequisite
from retasc.models.release_rule_state import ReleaseRuleState

SCHEMA_VERSION = 1


class Rule(BaseModel):
    """Rule for creating/managing Jira issues based on prerequisites."""

    class Config:
        frozen = True

    version: int = Field(
        description=f"The version of the rule schema. The latest version is {SCHEMA_VERSION}."
    )
    name: str = Field(description="The name of the rule.")
    prerequisites: list[Prerequisite] = Field(
        description="The prerequisites for the rule."
    )
    products: list[str] = Field(
        description="Affected Product Pages product short names",
        default_factory=lambda: ["rhel"],
    )

    def __hash__(self):
        return hash(self.name)

    @cache
    def update_state(self, context) -> ReleaseRuleState:
        """
        Return Completed only if all issues were closed, otherwise returns
        Pending if any prerequisites are Pending, and InProgress in other
        cases.
        """
        for prereq in self.prerequisites:
            with context.report.section(prereq.section_name()):
                state = prereq.update_state(context)
                if state != ReleaseRuleState.Completed:
                    context.report.set("state", state.name)
                context.prerequisites_state = min(context.prerequisites_state, state)
        return context.prerequisites_state
