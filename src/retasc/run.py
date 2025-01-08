# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import re
from collections import defaultdict
from collections.abc import Iterator

from retasc.jira_client import DryRunJiraClient, JiraClient
from retasc.models.config import Config
from retasc.models.parse_rules import parse_rules
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi
from retasc.report import Report
from retasc.requests_session import requests_session
from retasc.runtime_context import RuntimeContext
from retasc.templates.template_manager import TemplateManager

logger = logging.getLogger(__name__)

RE_VERSION = re.compile(r"^\w+-(?P<major>\d+)(?:[-.](?P<minor>\d+))?")


def rules_by_product(rules: dict[str, Rule]) -> dict[str, list[Rule]]:
    product_rules = defaultdict(list)
    for rule in rules.values():
        for product in rule.products:
            product_rules[product].append(rule)
    return product_rules


def parse_version(release: str) -> tuple[int, int]:
    """
    Parse version numbers (major, minor) from Product Pages release short name.
    """
    match = re.search(RE_VERSION, release)
    if not match:
        return 0, 0

    x = match.groupdict(default=0)
    return int(x["major"]), int(x["minor"])


def update_state(rule: Rule, context: RuntimeContext):
    with context.report.section(rule.name):
        context.prerequisites_state = ReleaseRuleState.Completed
        state = rule.update_state(context)
        context.report.set("state", state.name)


def iterate_rules(context: RuntimeContext) -> Iterator[tuple[str, str, list[Rule]]]:
    product_rules = rules_by_product(context.rules)
    for product, rules in product_rules.items():
        with context.report.section(product):
            releases = context.pp.active_releases(product)
            for release in releases:
                with context.report.section(release):
                    yield product, release, rules


def drop_issues(context: RuntimeContext):
    to_drop = [
        issue["key"]
        for issue in context.issues.values()
        if not issue["fields"]["resolution"]
    ]
    if not to_drop:
        return

    context.report.set("dropped_issues", to_drop)


def run(*, config: Config, jira_token: str, dry_run: bool) -> Report:
    session = requests_session()

    # Retry also on 401 to workaround for a Jira bug
    # https://github.com/atlassian-api/atlassian-python-api/issues/257
    jira_session = requests_session(retry_on_statuses=(401,))

    jira_cls = DryRunJiraClient if dry_run else JiraClient
    jira = jira_cls(api_url=config.jira_url, token=jira_token, session=jira_session)
    pp = ProductPagesApi(config.product_pages_url, session=session)
    rules = parse_rules(config.rules_path, config=config)
    template = TemplateManager(config.jira_template_path)
    report = Report()
    context = RuntimeContext(
        session=session,
        jira=jira,
        pp=pp,
        rules=rules,
        template=template,
        report=report,
        config=config,
    )

    for product, release, rules in iterate_rules(context):
        major, minor = parse_version(release)
        for rule in rules:
            context.release = release
            context.template.params = {
                "product": product,
                "release": release,
                "major": major,
                "minor": minor,
            }
            update_state(rule, context)

        drop_issues(context)

    if dry_run:
        logger.warning("To apply changes, run without --dry-run flag")

    return report
