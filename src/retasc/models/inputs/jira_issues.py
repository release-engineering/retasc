# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Iterator

from pydantic import Field

from retasc.models.inputs.base import InputBase


class JiraIssues(InputBase):
    """
    Jira issues.

    Adds the following template parameters if iterate_issues is true:
    - jira_issue - issue data
    - jira_issues - all issues matching the JQL query
    """

    jql: str = Field(description="JQL query for searching the issues")
    fields: list = Field(description="Jira issues fields to fetch")

    def values(self, context) -> Iterator[dict]:
        issues = context.jira.search_issues(jql=self.jql, fields=self.fields)
        for issue in issues:
            yield {
                "jira_issue": issue,
                "jira_issues": issues,
            }

    def section_name(self, values: dict) -> str:
        return f"JiraIssues({values['jira_issue']['key']!r})"
