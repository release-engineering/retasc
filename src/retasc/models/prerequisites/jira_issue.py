# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from collections.abc import Iterator
from itertools import takewhile
from textwrap import dedent
from typing import Any

from pydantic import Field

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.utils import to_comma_separated
from retasc.yaml import yaml

from .base import PrerequisiteBase

ISSUE_ID_DESCRIPTION = dedent("""
    Template for unique label name to identify the issue.

    Note: The label in Jira will be prefixed with "jira_label_prefix"
    configuration and suffixed with "jira_label_suffix" template variable
    (originates from rule inputs).

    Example: "add_beta_repos_for_{{ release }}"
""").strip()
TEMPLATE_PATH_DESCRIPTION = (
    "Path to the Jira issue template YAML file"
    ' relative to the "jira_template_path" configuration.'
)
FIELDS_DESCRIPTION = "Jira fields, override fields in the template"
JIRA_REQUIRED_FIELDS = frozenset(["labels", "resolution"])


def _is_resolved(issue: dict) -> bool:
    return issue["fields"]["resolution"] is not None


def _is_jira_field_up_to_date(current_value, new_value):
    if isinstance(current_value, dict) and isinstance(new_value, dict):
        return all(
            _is_jira_field_up_to_date(current_value.get(k), v)
            for k, v in new_value.items()
        )

    if isinstance(current_value, list) and isinstance(new_value, list):
        return len(current_value) == len(new_value) and all(
            _is_jira_field_up_to_date(current_value[i], new_value[i])
            for i in range(len(current_value))
        )

    return current_value == new_value


def _edit_issue(issue, fields, context, label: str):
    to_update = {
        k: v
        for k, v in fields.items()
        if k != "labels" and not _is_jira_field_up_to_date(issue["fields"][k], v)
    }

    # always keep the existing labels
    current_labels = set(issue["fields"]["labels"])
    labels = {label, *fields.get("labels", []), *current_labels}
    if not labels.issubset(current_labels):
        to_update["labels"] = sorted(labels)

    if not to_update:
        return

    context.report.current_data["update"] = to_update
    context.report.set("issue_status", "updated")
    context.jira.edit_issue(issue["key"], to_update)


def _report_jira_issue(issue: dict, jira_issue_id: str, context):
    context.report.jira_issues[jira_issue_id] = issue
    context.report.set("issue_id", issue["key"])
    context.report.current_data["issue_data"] = {
        k: v for k, v in issue["fields"].items() if v is not None
    }


def _create_issue(fields, context, label: str) -> dict:
    fields.setdefault("labels", []).append(label)
    context.report.set("issue_status", "created")
    return context.jira.create_issue(fields)


def _template_to_issue_data(template_data: dict, context) -> dict:
    fields = {context.config.to_jira_field_name(k): v for k, v in template_data.items()}

    labels = fields.get("labels", [])
    if not isinstance(labels, list):
        raise PrerequisiteUpdateStateError('Jira issue field "labels" must be a list')

    reserved_labels = {
        label for label in labels if label.startswith(context.config.jira_label_prefix)
    }
    if reserved_labels:
        label_list = to_comma_separated(reserved_labels)
        raise PrerequisiteUpdateStateError(
            "Jira issue labels must not use reserved prefix"
            f" {context.config.jira_label_prefix!r}: {label_list}"
        )

    return fields


def render_fields(value: Any, context) -> Any:
    """Render any strings nested in dicts and lists recursively as templates"""
    if isinstance(value, str):
        return context.template.render(value)

    if isinstance(value, dict):
        return {k: render_fields(v, context) for k, v in value.items()}

    if isinstance(value, list):
        return [render_fields(v, context) for v in value]

    return value


def _render_issue_template(
    template: str | None, jira_fields: dict[str, Any], context
) -> dict:
    if template is None:
        template_data = {}
    else:
        with open(context.config.jira_template_path / template) as f:
            template_content = f.read()

        content = context.template.render(template_content)
        template_data = yaml().load(content)

    template_data.update(render_fields(jira_fields, context))
    return _template_to_issue_data(template_data, context)


def _update_issue(
    jira_issue_id: str,
    template: str | None,
    jira_fields: dict[str, Any],
    must_exist: bool,
    context,
    parent_issue_key: str | None = None,
) -> dict | None:
    """
    Create and update Jira issue if needed.

    The issue is updated according to the template.

    Returns the managed Jira issue.
    """
    fields = _render_issue_template(template, jira_fields, context)

    if parent_issue_key is not None:
        fields["parent"] = {"key": parent_issue_key}

    supported_fields = JIRA_REQUIRED_FIELDS.union(fields.keys())
    label = f"{context.config.jira_label_prefix}{jira_issue_id}{context.template.params['jira_label_suffix']}"
    jql = f"labels={json.dumps(label)}"
    issues = context.jira.search_issues(jql=jql, fields=sorted(supported_fields))

    if issues:
        if len(issues) > 1:
            keys = to_comma_separated(issue["key"] for issue in issues)
            raise PrerequisiteUpdateStateError(
                f"Found multiple issues with the same ID label {label!r}: {keys}"
            )

        issue = issues[0]

        if not _is_resolved(issue):
            _edit_issue(issue, fields, context, label=label)
    elif must_exist:
        return None
    else:
        issue = _create_issue(fields, context, label=label)
        issue["fields"] = {"resolution": None, **fields}

    issue["fields"] = {
        context.config.from_jira_field_name(f): v for f, v in issue["fields"].items()
    }
    _report_jira_issue(issue, jira_issue_id, context)
    return issue


class JiraIssueTemplate(PrerequisiteBase):
    jira_issue: str = Field(description=ISSUE_ID_DESCRIPTION)
    template: str | None = Field(description=TEMPLATE_PATH_DESCRIPTION, default=None)
    fields: dict[str, Any] = Field(description=FIELDS_DESCRIPTION, default_factory=dict)
    must_exist: bool = Field(
        default=False,
        description=(
            "If True, the issue will not be created if it does not exist,"
            " only updated if it exists."
        ),
    )


class PrerequisiteJiraIssue(JiraIssueTemplate):
    """
    Prerequisite Jira issue.

    If the issue does not exist, ReTaSC will create it (unless "must_exist" is
    set to true) and keep it updated until it is resolved.

    The prerequisite state is InProgress until the Jira issue is resolved.
    After that, the state is Completed.

    Root directory for templates files is indicated with "jira_template_path"
    option in ReTaSC configuration, and "jira_fields" option declares supported
    Jira issue attributes allowed in the templates.
    """

    subtasks: list[JiraIssueTemplate] = Field(default_factory=list)

    def validate_inique_id(self, rules) -> str | None:
        own_issue_ids = set(jira_issue_ids(self))
        preceding_issue_ids = {
            issue_id
            for prereq in takewhile(
                lambda x: not x.must_exist and x is not self,
                jira_issue_prerequisites(rules),
            )
            for issue_id in jira_issue_ids(prereq)
        }
        duplicate_issue_ids = own_issue_ids.intersection(preceding_issue_ids)
        if duplicate_issue_ids:
            id_list = to_comma_separated(duplicate_issue_ids)
            return f"Jira issue ID(s) already used elsewhere: {id_list}"

        return None

    def validation_errors(self, rules, config) -> list[str]:
        errors = []

        missing_files = {
            file
            for file in template_paths(self)
            if not (config.jira_template_path / file).is_file()
        }
        if missing_files:
            file_list = to_comma_separated(missing_files)
            errors.append(f"Jira issue template files not found: {file_list}")

        # Check for duplicate issue IDs in the prerequisites
        if not self.must_exist:
            maybe_error = self.validate_inique_id(rules)
            if maybe_error:
                errors.append(maybe_error)

        return errors

    def update_state(self, context) -> ReleaseRuleState:
        """
        Return Completed only if the issue was resolved.

        If the issue exists or is created, it is stored as "jira_issue"
        template variable and added into "jira_issues" template dict with key
        matching the jira_issue.
        """
        context.template.params["jira_template_file"] = self.template
        jira_issue_id = context.template.render(self.jira_issue)
        context.report.set("jira_issue", jira_issue_id)
        issue = _update_issue(
            jira_issue_id, self.template, self.fields, self.must_exist, context
        )
        if issue is None:
            return ReleaseRuleState.InProgress
        context.template.params["jira_issue"] = issue
        if _is_resolved(issue):
            return ReleaseRuleState.Completed

        for subtask in self.subtasks:
            subtask_id = context.template.render(subtask.jira_issue)
            with context.report.section("subtasks", type="Subtask", name=subtask_id):
                context.report.set("jira_issue", subtask_id)
                _update_issue(
                    subtask_id,
                    subtask.template,
                    subtask.fields,
                    subtask.must_exist,
                    context,
                    parent_issue_key=issue["key"],
                )

        return ReleaseRuleState.InProgress


def templates_root() -> str:
    return os.getenv("RETASC_JIRA_TEMPLATES_ROOT", ".")


def template_filenames(prereq: PrerequisiteJiraIssue) -> Iterator[str]:
    if prereq.template is not None:
        yield prereq.template

    for x in prereq.subtasks:
        if x.template is not None:
            yield x.template


def template_paths(prereq: PrerequisiteJiraIssue) -> Iterator[str]:
    root = templates_root()
    for file in template_filenames(prereq):
        yield f"{root}/{file}"


def jira_issue_ids(prereq: PrerequisiteJiraIssue) -> Iterator[str]:
    yield prereq.jira_issue
    yield from (x.jira_issue for x in prereq.subtasks)


def jira_issue_prerequisites(rules):
    for rule in rules:
        for prereq in rule.prerequisites:
            if isinstance(prereq, PrerequisiteJiraIssue):
                yield prereq
    # Ignore this from coverage since rules is always non-empty and the
    # iteration always stops at a specific prerequisite.
    return  # pragma: no cover  # NOSONAR
