# SPDX-License-Identifier: GPL-3.0-or-later
import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache

from requests import Session

from retasc.jira import (
    JIRA_ISSUE_ID_LABEL_PREFIX,
    JIRA_LABEL,
    JIRA_MANAGED_FIELDS,
)
from retasc.jira_client import JiraClient
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi
from retasc.report import Report
from retasc.templates.template_manager import TemplateManager


def get_issue_id(issue):
    for label in issue["fields"]["labels"]:
        if label.startswith(JIRA_ISSUE_ID_LABEL_PREFIX):
            return label
    return f"retasc-no-id-{issue['key']}"


@dataclass
class RuntimeContext:
    rules: dict[str, Rule]
    jira: JiraClient
    pp: ProductPagesApi
    template: TemplateManager
    session: Session
    report: Report
    prerequisites_state: ReleaseRuleState = ReleaseRuleState.Pending

    release: str = ""

    def _issues(self) -> Iterator[tuple[str, dict]]:
        jql = f"labels={JIRA_LABEL} AND affectedVersion={json.dumps(self.release)}"
        issues = self.jira.search_issues(jql=jql, fields=JIRA_MANAGED_FIELDS)
        for issue in issues:
            issue_id = get_issue_id(issue)
            yield (issue_id, issue)

    @property
    @cache
    def issues(self) -> dict[str, dict]:
        return dict(self._issues())

    # Enable use in cached functions
    def __hash__(self):
        return hash(self.release)
