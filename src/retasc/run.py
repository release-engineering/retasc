# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from functools import cache

from retasc.jira_client import JiraClient
from retasc.models.parse_rules import parse_rules
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi

logger = logging.getLogger(__name__)

JIRA_LABEL = "retasc-managed"


@dataclass(frozen=True)
class RuntimeContext:
    rules: dict[str, Rule]
    jira: JiraClient
    pp: ProductPagesApi

    # Enable use in cached functions
    def __hash__(self):
        return id(self)


@cache
def jira_issues(jira: JiraClient, release: str) -> list[dict]:
    jql = f"labels={JIRA_LABEL} AND affectedVersion={json.dumps(release)}"
    return jira.search(jql=jql, fields=["labels", "resolution"])


def rules_by_release(context: RuntimeContext) -> dict[str, list[Rule]]:
    release_rules = defaultdict(list)
    for rule in context.rules.values():
        for product in rule.products:
            releases = context.pp.active_releases(product)
            for release in releases:
                release_rules[release].append(rule)
    return release_rules


def run(*, dry_run: bool, print=print):
    jira_url = os.environ["RETASC_JIRA_URL"]
    jira_token = os.environ["RETASC_JIRA_TOKEN"]
    pp_url = os.environ["RETASC_PP_URL"]
    path = os.environ["RETASC_RULES_PATH"]

    rules = parse_rules(path)

    jira = JiraClient(url=jira_url, token=jira_token)
    pp = ProductPagesApi(pp_url)

    context = RuntimeContext(jira=jira, pp=pp, rules=rules)

    release_rules = rules_by_release(context)

    for release, rules in release_rules.items():
        print(f"Release {release!r}")
        for rule in rules:
            # issues = jira_issues(jira, release)
            state = rule.state(context=context, release=release)
            print(f"  Rule {rule.name!r} state: {state.name}")

    if dry_run:
        logger.warning("To apply changes, run without --dry-run flag")
