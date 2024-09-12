# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import re
from collections import defaultdict

from retasc.jira_client import JiraClient
from retasc.models.parse_rules import parse_rules
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi
from retasc.runtime_context import RuntimeContext
from retasc.templates import TemplateManager

logger = logging.getLogger(__name__)

RE_VERSION = re.compile(r"(?:(\d+)[.-]){1,3}")


def rules_by_product(context: RuntimeContext) -> dict[str, list[Rule]]:
    product_rules = defaultdict(list)
    for rule in context.rules.values():
        for product in rule.products:
            product_rules[product].append(rule)
    return product_rules


def parse_version(release: str) -> tuple[int, int, int]:
    """
    Parse version numbers (major, minor, patch) from Product Pages release
    short name.
    """
    match = re.search(RE_VERSION, release)
    if not match:
        return 0, 0, 0

    x = [*match.groups(), 0, 0]
    return int(x[0]), int(x[1]), int(x[2])


def run(*, dry_run: bool, print=print):
    jira_url = os.environ["RETASC_JIRA_URL"]
    jira_token = os.environ["RETASC_JIRA_TOKEN"]
    pp_url = os.environ["RETASC_PP_URL"]
    path = os.environ["RETASC_RULES_PATH"]

    jira = JiraClient(url=jira_url, token=jira_token)
    pp = ProductPagesApi(pp_url)
    rules = parse_rules(path)
    template = TemplateManager()
    context = RuntimeContext(
        jira=jira, pp=pp, rules=rules, template=template, print=print
    )

    product_rules = rules_by_product(context)
    for product, rules in product_rules.items():
        print(f"Product {product!r}")
        releases = context.pp.active_releases(product)
        for release in releases:
            major, minor, patch = parse_version(release)
            print(f"- Release {release!r}")
            for rule in rules:
                context.release = release
                context.template.params = {
                    "product": product,
                    "release": release,
                    "major": major,
                    "minor": minor,
                    "patch": patch,
                }
                rule.update_params(context.template.params, context)
                state = rule.state(context)
                print(f"-- Rule {rule.name!r} state: {state.name}")

    if dry_run:
        logger.warning("To apply changes, run without --dry-run flag")
