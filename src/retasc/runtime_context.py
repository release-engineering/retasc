# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field

from requests import Session

from retasc.jira_client import JiraClient
from retasc.models.config import Config
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi
from retasc.report import Report
from retasc.templates.template_manager import TemplateManager


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

    @property
    def jira_issues(self) -> dict[str, dict]:
        return self.template.params.setdefault("jira_issues", {})

    @property
    def managed_jira_issues(self) -> dict[str, dict]:
        return self.template.params.setdefault("managed_jira_issues", {})

    @property
    def jira_labels(self) -> list[str]:
        return self.template.params.setdefault("jira_labels", [])
