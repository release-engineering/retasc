# SPDX-License-Identifier: GPL-3.0-or-later
import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from retasc.jira_client import JiraClient
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi
from retasc.templates import TemplateManager

JIRA_LABEL = "retasc-managed"

type PrintCallback = Callable[[str], None]


@dataclass
class RuntimeContext:
    rules: dict[str, Rule]
    jira: JiraClient
    pp: ProductPagesApi
    template: TemplateManager
    print: PrintCallback

    release: str = ""

    @property
    @cache
    def closed_issue_labels(self) -> set[str]:
        return {
            label
            for issue in self.issues
            for label in issue["fields"]["labels"]
            if issue["fields"]["resolution"] is not None
        }

    @property
    @cache
    def issues(self) -> list[dict]:
        jql = f"labels={JIRA_LABEL} AND affectedVersion={json.dumps(self.release)}"
        return self.jira.search(jql=jql, fields=["labels", "resolution"])

    # Enable use in cached functions
    def __hash__(self):
        return hash(self.release)
