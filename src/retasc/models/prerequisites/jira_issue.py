# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from collections.abc import Iterator
from itertools import takewhile
from textwrap import dedent

from pydantic import BaseModel, Field

from retasc.models.release_rule_state import ReleaseRuleState
from retasc.utils import to_comma_separated
from retasc.yaml import yaml

from .base import PrerequisiteBase

ISSUE_ID_DESCRIPTION = dedent("""
    Template for unique label name to identify the issue.

    Note: The label in Jira will be prefixed with "jira_label_prefix"
    configuration.

    Example: "add_beta_repos_for_{{ release }}"
""").strip()
TEMPLATE_PATH_DESCRIPTION = (
    "Path to the Jira issue template YAML file"
    ' relative to the "jira_template_path" configuration.'
)
JIRA_REQUIRED_FIELDS = frozenset(["labels", "resolution"])


def _is_resolved(issue: dict) -> bool:
    return issue["fields"]["resolution"] is not None


def _set_parent_issue(fields: dict, parent_issue_key: str | None = None):
    if parent_issue_key is not None:
        fields["parent"] = {"key": parent_issue_key}


def _is_jira_field_up_to_date(current_value, new_value):
    if isinstance(current_value, dict) and isinstance(new_value, dict):
        return all(
            _is_jira_field_up_to_date(current_value.get(k), v)
            for k, v in new_value.items()
        )

    return current_value == new_value


def _edit_issue(
    issue, fields, context, label: str, parent_issue_key: str | None = None
):
    to_update = {
        k: v
        for k, v in fields.items()
        if k != "labels" and not _is_jira_field_up_to_date(issue["fields"][k], v)
    }

    labels = {label, *fields.get("labels", [])}
    current_labels = set(issue["fields"]["labels"])
    if labels != current_labels:
        to_update["labels"] = sorted(labels)

    if not to_update:
        return

    context.report.set("update", json.dumps(to_update))
    _set_parent_issue(to_update, parent_issue_key)
    context.jira.edit_issue(issue["key"], to_update)


def _report_jira_issue(issue: dict, jira_issue_id: str, context):
    context.report.jira_issues[jira_issue_id] = issue
    context.report.set("issue", issue["key"])


def _create_issue(
    fields, context, label: str, parent_issue_key: str | None = None
) -> dict:
    fields.setdefault("labels", []).append(label)
    context.report.set("create", json.dumps(fields))
    _set_parent_issue(fields, parent_issue_key)
    return context.jira.create_issue(fields)


def _template_to_issue_data(template_data: dict, context, template: str) -> dict:
    fields = {context.config.to_jira_field_name(k): v for k, v in template_data.items()}

    reserved_labels = {
        label
        for label in fields.get("labels", [])
        if label.startswith(context.config.jira_label_prefix)
    }
    if reserved_labels:
        label_list = to_comma_separated(reserved_labels)
        raise RuntimeError(
            f"Jira template {template!r} must not use labels prefixed with"
            f" {context.config.jira_label_prefix!r}: {label_list}"
        )

    return fields


def _render_issue_template(template: str, context) -> dict:
    with open(context.config.jira_template_path / template) as f:
        template_content = f.read()

    content = context.template.render(template_content)
    template_data = yaml().load(content)
    return _template_to_issue_data(template_data, context, template)


def _update_issue(
    jira_issue_id: str, template: str, context, parent_issue_key: str | None = None
) -> dict:
    """
    Create and update Jira issue if needed.

    The issue is updated according to the template.

    Returns the managed Jira issue.
    """
    fields = _render_issue_template(template, context)

    supported_fields = JIRA_REQUIRED_FIELDS.union(fields.keys())
    label = f"{context.config.jira_label_prefix}{jira_issue_id}"
    jql = f"labels={json.dumps(label)}"
    issues = context.jira.search_issues(jql=jql, fields=sorted(supported_fields))

    if issues:
        if len(issues) > 1:
            keys = to_comma_separated(issue["key"] for issue in issues)
            raise RuntimeError(
                f"Found multiple issues with the same ID label {label!r}: {keys}"
            )

        issue = issues[0]

        if not _is_resolved(issue):
            _edit_issue(
                issue, fields, context, label=label, parent_issue_key=parent_issue_key
            )
    else:
        issue = _create_issue(
            fields, context, label=label, parent_issue_key=parent_issue_key
        )
        issue["fields"] = {"resolution": None, **fields}

    issue["fields"] = {
        context.config.from_jira_field_name(f): v for f, v in issue["fields"].items()
    }
    _report_jira_issue(issue, jira_issue_id, context)
    return issue


class JiraIssueTemplate(BaseModel):
    id: str = Field(description=ISSUE_ID_DESCRIPTION)
    template: str = Field(description=TEMPLATE_PATH_DESCRIPTION)


class PrerequisiteJiraIssue(PrerequisiteBase):
    """
    Prerequisite Jira issue.

    If the issue does not exist, ReTaSC will create it and keep it updated
    until it is resolved.

    The prerequisite state is InProgress until the Jira issue is resolved.
    After that, the state is Completed.

    Root directory for templates files is indicated with "jira_template_path"
    option in ReTaSC configuration, and "jira_fields" option declares supported
    Jira issue attributes allowed in the templates.
    """

    jira_issue_id: str = Field(description=ISSUE_ID_DESCRIPTION)
    template: str = Field(description=TEMPLATE_PATH_DESCRIPTION)
    subtasks: list[JiraIssueTemplate] = Field(default_factory=list)

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

        own_issue_ids = set(jira_issue_ids(self))
        preceding_issue_ids = {
            issue_id
            for prereq in takewhile(
                lambda x: x is not self, jira_issue_prerequisites(rules)
            )
            for issue_id in jira_issue_ids(prereq)
        }
        duplicate_issue_ids = own_issue_ids.intersection(preceding_issue_ids)
        if duplicate_issue_ids:
            id_list = to_comma_separated(duplicate_issue_ids)
            errors.append(f"Jira issue ID(s) already used elsewhere: {id_list}")

        return errors

    def update_state(self, context) -> ReleaseRuleState:
        """
        Return Completed only if the issue was resolved.

        If the issue exists or is created, it is added into "issues" dict
        template parameter (dict key is jira_issue_id).
        """
        jira_issue_id = context.template.render(self.jira_issue_id)
        issue = _update_issue(jira_issue_id, self.template, context)
        if _is_resolved(issue):
            return ReleaseRuleState.Completed

        for subtask in self.subtasks:
            subtask_id = context.template.render(subtask.id)
            with context.report.section(f"Subtask({subtask_id!r})"):
                _update_issue(
                    subtask_id, subtask.template, context, parent_issue_key=issue["key"]
                )

        return ReleaseRuleState.InProgress

    def section_name(self, context) -> str:
        jira_issue_id = context.template.render(self.jira_issue_id)
        return f"Jira({jira_issue_id!r})"


def templates_root() -> str:
    return os.getenv("RETASC_JIRA_TEMPLATES_ROOT", ".")


def template_filenames(prereq: PrerequisiteJiraIssue) -> Iterator[str]:
    yield prereq.template
    for x in prereq.subtasks:
        yield x.template


def template_paths(prereq: PrerequisiteJiraIssue) -> Iterator[str]:
    root = templates_root()
    for file in template_filenames(prereq):
        yield f"{root}/{file}"


def jira_issue_ids(prereq: PrerequisiteJiraIssue) -> Iterator[str]:
    yield prereq.jira_issue_id
    for x in prereq.subtasks:
        yield x.id


def jira_issue_prerequisites(rules):
    for rule in rules:
        for prereq in rule.prerequisites:
            if isinstance(prereq, PrerequisiteJiraIssue):
                yield prereq
    # Ignore this from coverage since rules is always non-empty and the
    # iteration always stops at a specific prerequisite.
    return  # pragma: no cover  # NOSONAR
