# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from collections.abc import Generator
from datetime import date

from pydantic import BaseModel

from retasc.jira_client import JiraClient
from retasc.models.parse_rules import parse_rules
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi

logger = logging.getLogger(__name__)

type Schedule = dict[str, date]


class ReleaseRule(BaseModel):
    """
    Represents application of a specific Rule for a specific product release.
    """

    rule: Rule
    release: str
    state: ReleaseRuleState


class RuntimeContext(BaseModel):
    rules: list[Rule]
    jira: JiraClient
    pp: ProductPagesApi


def get_release_rule_state(rule, **kwargs):
    result = ReleaseRuleState.Completed
    for prereq in rule.prerequisites:
        result = min(result, prereq.state(**kwargs))
        if result == ReleaseRuleState.Pending:
            return ReleaseRuleState.Pending
    return result


def collect_tasks(context: RuntimeContext) -> Generator[ReleaseRule]:
    for rule in context.rules:
        for product in rule.products:
            releases = context.pp.active_releases(product)
            for release in releases:
                state = get_release_rule_state(
                    rule=rule, context=context, release=release
                )
                yield ReleaseRule(rule=rule, release=release, state=state)


def run(*, dry_run: bool):
    jira_url = os.environ["RETASC_JIRA_URL"]
    jira_token = os.environ["RETASC_JIRA_TOKEN"]
    pp_url = os.environ["RETASC_PP_URL"]
    path = os.environ["RETASC_RULES_PATH"]

    rules = parse_rules(path)

    jira = JiraClient(url=jira_url, token=jira_token)
    pp = ProductPagesApi(pp_url)

    context = RuntimeContext(jira=jira, pp=pp, rules=rules)

    tasks = list(collect_tasks(context))

    if dry_run:
        print("\n".join(str(task) for task in tasks))
        return

    for task in tasks:
        task.apply(jira)
