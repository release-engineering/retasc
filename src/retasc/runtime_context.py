# SPDX-License-Identifier: GPL-3.0-or-later
import json
from collections.abc import Iterator
from dataclasses import dataclass, field

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


def get_issues(jira, jira_labels, config) -> Iterator[tuple[str, dict]]:
    jql = " AND ".join(f"labels={json.dumps(label)}" for label in jira_labels)
    supported_fields = list(JIRA_REQUIRED_FIELDS.union(config.jira_fields.values()))
    issues = jira.search_issues(jql=jql, fields=supported_fields)
    for issue in issues:
        issue_id = get_issue_id(issue, label_prefix=config.jira_label_prefix)
        yield (issue_id, issue)


@dataclass
class RuntimeContext:
    rules: dict[str, Rule]
    jira: JiraClient
    pp: ProductPagesApi
    template: TemplateManager
    session: Session
    report: Report
    config: Config

    rules_states: dict[str, ReleaseRuleState] = field(default_factory=dict)
    issues_cache: dict = field(default_factory=dict)

    @property
    def issues(self) -> dict[str, dict]:
        labels = tuple(self.jira_labels)
        issues = self.issues_cache.get(labels)
        if issues is None:
            issues = dict(get_issues(self.jira, labels, self.config))
            self.issues_cache[labels] = issues
        return issues

    @property
    def jira_labels(self) -> list[str]:
        return [
            self.template.render(template)
            for template in self.config.jira_label_templates
        ]
