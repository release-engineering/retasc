# SPDX-License-Identifier: GPL-3.0-or-later
import json
from functools import cache

from pydantic import BaseModel, Field

from retasc.jira_client import JiraClient
from retasc.models.jira_issue import JiraIssueTemplate
from retasc.models.prerequisites import Prerequisite
from retasc.models.release_rule_state import ReleaseRuleState

SCHEMA_VERSION = 1


def is_closed(*, jira: JiraClient, label: str, release: str) -> bool:
    jql = (
        f"labels={label} AND affectedVersion={json.dumps(release)}"
        " AND resolution IS NOT EMPTY"
    )
    issues = jira.search(jql=jql, fields=[], limit=1)
    return issues != []


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

    def __hash__(self):
        return self.name.__hash__()

    @cache
    def state(self, *, context, release) -> ReleaseRuleState:
        """
        Returns Completed only if all issues were closed.
        """
        all_issues_closed = all(
            is_closed(jira=context.jira, label=template.label, release=release)
            for template in self.jira_issues
        )
        if all_issues_closed:
            return ReleaseRuleState.Completed

        result = ReleaseRuleState.InProgress
        for prereq in self.prerequisites:
            result = min(result, prereq.state(context=context, release=release))
            if result == ReleaseRuleState.Pending:
                return ReleaseRuleState.Pending
        return result
