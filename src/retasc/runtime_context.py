# SPDX-License-Identifier: GPL-3.0-or-later
import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache

from requests import Session

from retasc.jira_client import JiraClient
from retasc.models.config import Config
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi
from retasc.report import Report
from retasc.templates.template_manager import TemplateManager

JIRA_REQUIRED_FIELDS = frozenset(["labels", "resolution"])


def get_issue_id(issue, *, label_prefix):
    for label in issue["fields"]["labels"]:
        if label.startswith(label_prefix):
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
    config: Config
    prerequisites_state: ReleaseRuleState = ReleaseRuleState.Pending

    release: str = ""

    def _issues(self) -> Iterator[tuple[str, dict]]:
        jql = " AND ".join(f"labels={json.dumps(label)}" for label in self.jira_labels)
        supported_fields = list(
            JIRA_REQUIRED_FIELDS.union(self.config.jira_fields.values())
        )
        issues = self.jira.search_issues(jql=jql, fields=supported_fields)
        for issue in issues:
            issue_id = get_issue_id(issue, label_prefix=self.config.jira_label_prefix)
            yield (issue_id, issue)

    @property
    @cache
    def issues(self) -> dict[str, dict]:
        return dict(self._issues())

    @property
    @cache
    def jira_labels(self) -> list[str]:
        return [
            self.template.render(template)
            for template in self.config.jira_label_templates
        ]

    # Enable use in cached functions
    def __hash__(self):
        return hash(self.release)
