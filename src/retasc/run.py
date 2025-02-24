# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging
from collections.abc import Iterator

from opentelemetry import trace

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
tracer = trace.get_tracer(__name__)


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


def run_helper(
    *, config: Config, jira_token: str, jira_cls: type[JiraClient | DryRunJiraClient]
) -> Report:
    session = requests_session()

    # Retry also on 401 to workaround for a Jira bug
    # https://github.com/atlassian-api/atlassian-python-api/issues/257
    jira_session = requests_session(retry_on_statuses=(401,))

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
            context.template.params["config"] = context.config
            context.template.params["report"] = context.report.data
            context.template.params["jira_issues"] = context.report.jira_issues
            update_state(rule, context)

    return report


@tracer.start_as_current_span("run")
def run(*, config: Config, jira_token: str) -> Report:
    return run_helper(config=config, jira_token=jira_token, jira_cls=JiraClient)


@tracer.start_as_current_span("dry_run")
def dry_run(*, config: Config, jira_token: str) -> Report:
    report = run_helper(config=config, jira_token=jira_token, jira_cls=DryRunJiraClient)
    logger.warning("To apply changes, run without --dry-run flag")
    return report
