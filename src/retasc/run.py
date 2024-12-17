# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging
from collections.abc import Iterator

from retasc.jira_client import DryRunJiraClient, JiraClient
from retasc.models.config import Config
from retasc.models.inputs.base import InputBase
from retasc.models.parse_rules import parse_rules
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesApi
from retasc.report import Report
from retasc.requests_session import requests_session
from retasc.runtime_context import RuntimeContext
from retasc.templates.template_manager import TemplateManager

logger = logging.getLogger(__name__)


def rules_by_input(context: RuntimeContext) -> list[tuple[InputBase, dict, list[Rule]]]:
    result: dict[str, tuple[InputBase, dict, list[Rule]]] = {}
    input_values_cache: dict[str, list[dict]] = {}

    for rule in context.rules.values():
        for input in rule.inputs:
            cache_key = input.model_dump_json()
            input_values = input_values_cache.get(cache_key)
            if input_values is None:
                input_values = list(input.values(context))
                input_values_cache[cache_key] = input_values

            for values in input_values:
                key = json.dumps(values)
                _, _, rules_for_input = result.setdefault(key, (input, values, []))
                rules_for_input.append(rule)

    return list(result.values())


def update_state(rule: Rule, context: RuntimeContext):
    with context.report.section(rule.name):
        state = rule.update_state(context)
        context.report.set("state", state.name)


def iterate_rules(context: RuntimeContext) -> Iterator[tuple[dict, list[Rule]]]:
    input_rules = rules_by_input(context)
    for input, values, rules in input_rules:
        context.rules_states = {}
        with context.report.section(input.section_name(values)):
            yield values, rules


def drop_issues(context: RuntimeContext):
    to_drop = [
        issue["key"]
        for issue_id, issue in context.jira_issues.items()
        if not issue["fields"]["resolution"]
        and issue_id not in context.managed_jira_issues
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

    for input, rules in iterate_rules(context):
        for rule in rules:
            context.template.params = input.copy()
            update_state(rule, context)

        drop_issues(context)

    if dry_run:
        logger.warning("To apply changes, run without --dry-run flag")

    return report
