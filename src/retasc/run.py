# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from datetime import date
from functools import cache
from typing import Iterable, Literal

from retasc.jira_client import JiraClient, JiraIssue
from retasc.product_pages_api import ProductPagesApi
from retasc.validator.models import Rule
from retasc.validator.parse_rules import parse_rules

logger = logging.getLogger(__name__)

JIRA_LABEL = "retasc-managed"

type State = Literal[
    "Pending",
    "InProgress",
    "Completed",
]


class Task:
    def apply(self, jira: JiraClient, jira_issues: list[JiraIssue]):
        pass


@cache
def active_releases_schedules(
    product_name: str, pp: ProductPagesApi
) -> dict[str, dict[str, date]]:
    releases = pp.active_releases(product_name)
    return {r: pp.release_schedules(r) for r in releases}


def collect_jira_issues(jira: JiraClient) -> list[JiraIssue]:
    return jira.search(jql=f"label='{JIRA_LABEL}' AND resolution is EMPTY")


def collect_tasks(rules: Iterable[Rule], pp: ProductPagesApi) -> list[Task]:
    for rule in rules:
        schedules = active_releases_schedules(rule.prerequisites.pp_product, pp)

    return []


def run(*, dry_run: bool):
    url = os.environ["RETASC_JIRA_URL"]
    token = os.environ["RETASC_JIRA_TOKEN"]
    jira = JiraClient(url=url, token=token)

    url = os.environ["RETASC_PP_URL"]
    pp = ProductPagesApi(url)

    path = os.environ["RETASC_RULES_PATH"]
    rules = parse_rules(path)
    jira_issues = collect_jira_issues(jira)

    tasks = collect_tasks(rules.values(), pp)

    if dry_run:
        print("\n".join(str(task) for task in tasks))
        return

    for task in tasks:
        task.apply(jira, jira_issues)
