# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Iterator

from pydantic import Field

from retasc.models.inputs.base import InputBase

JIRA_REQUIRED_FIELDS = frozenset(["labels", "resolution"])


def get_issue_id(issue, label_prefix):
    for label in issue["fields"]["labels"]:
        if label.startswith(label_prefix):
            return label[len(label_prefix) :]
    return f"retasc-no-id-{issue['key']}"


def get_issues(jql: str, context) -> dict[str, dict]:
    supported_fields = list(
        JIRA_REQUIRED_FIELDS.union(context.config.jira_fields.values())
    )
    issues = context.jira.search_issues(jql=jql, fields=sorted(supported_fields))
    return {
        get_issue_id(issue, context.config.jira_label_prefix): issue for issue in issues
    }


class JiraIssues(InputBase):
    """
    Jira issues.

    Adds the following template parameters if iterate_issues is true:
    - jira_issue - issue data
    - jira_issue_id - ReTaSC ID of the issue, based on label prefixed with
      Config.jira_label_prefix
    - jira_issues - all issues matching the JQL query
    """

    jql: str = Field(description="JQL query for searching the issues")

    def values(self, context) -> Iterator[dict]:
        issues = get_issues(self.jql, context)
        for issue_id, data in issues.items():
            yield {
                "jira_issue_id": issue_id,
                "jira_issue": data,
                "jira_issues": issues,
                "jql": self.jql,
                "managed_jira_issues": issues,
            }

    def section_name(self, values: dict) -> str:
        return f"JiraIssues({values['jira_issue']['key']!r})"
