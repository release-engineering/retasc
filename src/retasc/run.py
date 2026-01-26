# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging
import os
from collections.abc import Iterator
from http.cookiejar import MozillaCookieJar

from jinja2.exceptions import TemplateError
from opentelemetry import trace
from requests import Session
from requests.exceptions import RequestException

from retasc.jira_client import DryRunJiraClient, JiraClient
from retasc.models.config import Config
from retasc.models.inputs.base import InputBase
from retasc.models.inputs.exceptions import InputValuesError
from retasc.models.parse_rules import parse_rules
from retasc.models.rule import Rule
from retasc.openshift_client import OpenShiftClient
from retasc.product_pages_api import ProductPagesApi
from retasc.report import Report
from retasc.requests_session import requests_session
from retasc.runtime_context import RuntimeContext
from retasc.templates.template_manager import TemplateManager

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def get_inputs(input, context: RuntimeContext) -> list:
    try:
        return list(input.values(context))
    except RequestException as e:
        section = type(input).__name__
        with context.report.section("inputs", type=section, name=""):
            context.report.add_request_error(e)
    except (InputValuesError, TemplateError) as e:
        section = type(input).__name__
        with context.report.section("inputs", type=section, name=""):
            context.report.add_error(str(e))
    return []


def rules_by_input(context: RuntimeContext) -> list[tuple[InputBase, dict, list[Rule]]]:
    result: dict[str, tuple[InputBase, dict, list[Rule]]] = {}
    input_values_cache: dict[str, list[dict]] = {}

    for rule in context.rules.values():
        for input in rule.inputs:
            cache_key = input.model_dump_json()
            input_values = input_values_cache.get(cache_key)
            if input_values is None:
                input_values = get_inputs(input, context)
                input_values_cache[cache_key] = input_values

            for values in input_values:
                key = json.dumps({k: repr(v) for k, v in values.items()})
                _, _, rules_for_input = result.setdefault(key, (input, values, []))
                rules_for_input.append(rule)

    return list(result.values())


def update_state(rule: Rule, context: RuntimeContext):
    with context.report.section("rules", type="Rule", name=rule.name):
        del context.report.current_data["type"]
        state = rule.update_state(context)
        context.report.set("state", state.name)


def iterate_rules(context: RuntimeContext) -> Iterator[tuple[dict, list[Rule]]]:
    input_rules = rules_by_input(context)
    for input, values, rules in input_rules:
        context.rule_template_params = {}
        section = type(input).__name__
        report_vars = input.report_vars(values)
        name = " ".join(str(x) for x in report_vars.values())
        with context.report.section("inputs", type=section, name=name):
            context.report.current_data.update(report_vars)
            yield values, rules


@tracer.start_as_current_span("oidc_token")
def oidc_token(oidc_token_url: str, session: Session) -> str:
    token_response = session.post(
        oidc_token_url,
        {
            "grant_type": "client_credentials",
            "client_id": os.getenv("RETASC_OIDC_CLIENT_ID"),
            "client_secret": os.getenv("RETASC_OIDC_CLIENT_SECRET"),
        },
        headers={"Content-type": "application/x-www-form-urlencoded"},
    )

    if not token_response.ok:
        logger.error("Failed to get OIDC token: %s", token_response.text)
        token_response.raise_for_status()

    return token_response.json()["access_token"]


def _init_product_pages_session(config: Config, session: Session) -> Session:
    """Initialize Product Pages session with authentication."""
    pp_cookies = os.getenv("RETASC_PRODUCT_PAGES_COOKIES")
    if pp_cookies:
        cookiejar = MozillaCookieJar()
        cookiejar.load(pp_cookies)
        return requests_session(
            connect_timeout=config.connect_timeout,
            read_timeout=config.connect_timeout,
            cookies=cookiejar,
        )

    if config.oidc_token_url is not None:
        pp_session = requests_session(
            connect_timeout=config.connect_timeout, read_timeout=config.connect_timeout
        )
        token = oidc_token(config.oidc_token_url, pp_session)
        pp_session.headers["Authorization"] = f"Bearer {token}"
        return pp_session

    return session


def _init_openshift_client(config: Config, session: Session) -> OpenShiftClient | None:
    """Initialize OpenShift client if configured."""
    if not config.openshift_api_url:
        return None

    openshift_token = os.getenv("RETASC_OPENSHIFT_TOKEN")
    if not openshift_token:
        return None

    return OpenShiftClient(
        api_url=config.openshift_api_url,
        token=openshift_token,
        session=session,
    )


def run_helper(
    *,
    config: Config,
    jira_cls: type[JiraClient | DryRunJiraClient],
    rule_files: list[str],
    jira_token: str | None = None,
    jira_password: str | None = None,
    jira_username: str | None = None,
) -> Report:
    session = requests_session(
        connect_timeout=config.connect_timeout, read_timeout=config.connect_timeout
    )

    pp_session = _init_product_pages_session(config, session)

    # Retry also on 401 to workaround for a Jira bug
    # https://github.com/atlassian-api/atlassian-python-api/issues/257
    jira_session = requests_session(
        connect_timeout=config.jira_connect_timeout,
        read_timeout=config.jira_connect_timeout,
        retry_on_statuses=(401,),
    )

    jira = jira_cls(
        api_url=config.jira_url,
        token=jira_token,
        username=jira_username,
        password=jira_password,
        cloud=config.jira_cloud,
        session=jira_session,
    )
    pp = ProductPagesApi(config.product_pages_url, session=pp_session)
    openshift = _init_openshift_client(config, session)

    rules = {
        k: v
        for rule_path in rule_files
        for k, v in parse_rules(rule_path, config=config).items()
    }
    template = TemplateManager(
        template_search_path=config.jira_template_path,
        template_extensions=config.template_extensions,
    )
    report = Report()
    context = RuntimeContext(
        session=session,
        jira=jira,
        pp=pp,
        rules=rules,
        template=template,
        report=report,
        config=config,
        openshift=openshift,
    )
    context.template.env.globals["retasc_context"] = context

    for input, input_rules in iterate_rules(context):
        for rule in input_rules:
            context.template.params = input.copy()
            context.template.params["config"] = context.config
            context.template.params["report"] = context.report.data
            context.template.params["jira_issues"] = context.report.jira_issues
            context.template.params["jira"] = context.jira
            update_state(rule, context)

    return report


@tracer.start_as_current_span("run")
def run(*, config: Config, rule_files: list[str], **kwargs) -> Report:
    return run_helper(
        config=config,
        jira_cls=JiraClient,
        rule_files=rule_files,
        **kwargs,
    )


@tracer.start_as_current_span("dry_run")
def dry_run(*, config: Config, rule_files: list[str], **kwargs) -> Report:
    report = run_helper(
        config=config,
        jira_cls=DryRunJiraClient,
        rule_files=rule_files,
        **kwargs,
    )
    logger.warning("To apply changes, run without --dry-run flag")
    return report
