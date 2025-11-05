# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field

from requests import Session

from retasc.jira_client import JiraClient
from retasc.models.config import Config
from retasc.models.rule import Rule
from retasc.openshift_client import OpenShiftClient
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
    openshift: OpenShiftClient | None = None

    rule_template_params: dict[str, dict] = field(default_factory=dict)
