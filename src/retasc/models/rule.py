# SPDX-License-Identifier: GPL-3.0-or-later
from functools import cache
from typing import Any

from pydantic import BaseModel, Field

from retasc.models.jira_issue import JiraIssueTemplate
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
    jira_issues: list[JiraIssueTemplate] = Field(
        description="The jira issues to create and manager for the rule."
    )
    products: list[str] = Field(
        description="Affected Product Pages product short names",
        default_factory=lambda: ["rhel"],
    )
    params: dict[str, Any] = Field(
        description="Additional parameters for templates",
        default_factory=dict,
    )

    def __hash__(self):
        return hash(self.name)

    def update_params(self, params: dict, context):
        """Update template parameters"""
        params.update(self.params)
        for prereq in self.prerequisites:
            prereq.update_params(params, context)
        return params

    @cache
    def state(self, context) -> ReleaseRuleState:
        """
        Returns Completed only if all issues were closed.
        """
        all_issues_closed = all(
            template.label in context.closed_issue_labels
            for template in self.jira_issues
        )
        if all_issues_closed:
            return ReleaseRuleState.Completed

        result = ReleaseRuleState.InProgress
        for prereq in self.prerequisites:
            result = min(result, prereq.state(context))
            if result == ReleaseRuleState.Pending:
                return ReleaseRuleState.Pending
        return result
