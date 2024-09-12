# SPDX-License-Identifier: GPL-3.0-or-later
import json

from pydantic import BaseModel, Field

from retasc.jira_client import JiraClient
from retasc.models.release_rule_state import ReleaseRuleState


def is_closed(*, jira: JiraClient, label: str, release: str) -> bool:
    jql = (
        f"labels={label} AND affectedVersion={json.dumps(release)}"
        " AND resolution IS NOT EMPTY"
    )
    issues = jira.search(jql=jql, fields=[], limit=1)
    return issues != []


class PrerequisiteRule(BaseModel):
    """Prerequisite Rule."""

    rules: list[str] = Field(
        default=[],
        description="The prerequisite rule",
    )

    def state(self, *, context, release, rule, **_kwargs) -> ReleaseRuleState:
        """
        Returns Completed only if all issues were closed.
        """
        all_closed = all(
            is_closed(jira=context.jira, label=template.label, release=release)
            for template in rule.jira_issues
        )
        return ReleaseRuleState.Completed if all_closed else ReleaseRuleState.Pending
