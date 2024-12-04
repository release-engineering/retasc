# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from collections.abc import Iterator
from itertools import takewhile

from pydantic import BaseModel, Field

from retasc.models.release_rule_state import ReleaseRuleState
from retasc.utils import to_comma_separated
from retasc.yaml import yaml

from .base import PrerequisiteBase

ISSUE_ID_DESCRIPTION = "Unique identifier for the issue."
TEMPLATE_PATH_DESCRIPTION = (
    "Path to the Jira issue template YAML file"
    ' relative to the "jira_template_path" configuration.'
)


def _is_resolved(issue: dict) -> bool:
    return issue["fields"]["resolution"] is not None


def _set_parent_issue(fields: dict, parent_issue_key: str | None = None):
    if parent_issue_key is not None:
        fields["parent"] = {"key": parent_issue_key}


def _edit_issue(
    issue, fields, context, label: str, parent_issue_key: str | None = None
):
    to_update = {
        k: v for k, v in fields.items() if issue["fields"][k] != v and k != "labels"
    }

    required_labels = {label, *context.jira_labels}
    labels = required_labels.union(fields.get("labels", []))
    current_labels = set(issue["fields"]["labels"])
    if labels != current_labels:
        to_update["labels"] = sorted(labels)

    if not to_update:
        return

    context.report.set("update", json.dumps(to_update))
    _set_parent_issue(to_update, parent_issue_key)
    context.jira.edit_issue(issue["key"], to_update)


def _report_jira_issue(issue: dict, jira_issue_id: str, context):
    issues_params = context.template.params.setdefault("issues", {})
    issues_params[jira_issue_id] = issue
    context.report.set("issue", issue["key"])


def _create_issue(
    fields, context, label: str, parent_issue_key: str | None = None
) -> dict:
    context.report.set("create", json.dumps(fields))
    _set_parent_issue(fields, parent_issue_key)
    fields.setdefault("labels", []).extend([label, *context.jira_labels])
    return context.jira.create_issue(fields)


def _template_to_issue_data(template_data: dict, context, template: str) -> dict:
    unsupported_fields = [
        name for name in template_data if name not in context.config.jira_fields
    ]
    if unsupported_fields:
        field_list = to_comma_separated(unsupported_fields)
        supported_fields = to_comma_separated(context.config.jira_fields)
        raise RuntimeError(
            f"Jira template {template!r} contains unsupported fields: {field_list}"
            f"\nSupported fields: {supported_fields}"
        )

    fields = {context.config.jira_fields[k]: v for k, v in template_data.items()}

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


def _update_issue(
    jira_issue_id: str, template: str, context, parent_issue_key: str | None = None
) -> dict:
    """
    Create and update Jira issue if needed.

    The issue is updated according to the template.

    Returns the managed Jira issue.
    """
    label = f"{context.config.jira_label_prefix}{jira_issue_id}"
    issue = context.issues.pop(label, None)

    if issue:
        _report_jira_issue(issue, jira_issue_id, context)
        if _is_resolved(issue):
            return issue

    with open(context.config.jira_template_path / template) as f:
        template_content = f.read()

    content = context.template.render(template_content)
    template_data = yaml().load(content)
    fields = _template_to_issue_data(template_data, context, template)

    if issue:
        _edit_issue(
            issue, fields, context, label=label, parent_issue_key=parent_issue_key
        )
        return issue

    issue = _create_issue(
        fields, context, label=label, parent_issue_key=parent_issue_key
    )
    _report_jira_issue(issue, jira_issue_id, context)
    return issue


class JiraIssueTemplate(BaseModel):
    id: str = Field(description=ISSUE_ID_DESCRIPTION)
    template: str = Field(description=TEMPLATE_PATH_DESCRIPTION)


class PrerequisiteJiraIssue(PrerequisiteBase):
    """
    Prerequisite Jira issue.

    If the issue does not exist, the issue is created. Otherwise, it is updated
    if it is not yet resolved.

    After the Jira issue is resolved the prerequisite state is Completed,
    otherwise it is InProgress.

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
        issue = _update_issue(self.jira_issue_id, self.template, context)
        if _is_resolved(issue):
            return ReleaseRuleState.Completed

        for subtask in self.subtasks:
            with context.report.section(f"Subtask({subtask.id!r})"):
                _update_issue(
                    subtask.id, subtask.template, context, parent_issue_key=issue["key"]
                )

        return ReleaseRuleState.InProgress

    def section_name(self) -> str:
        return f"Jira({self.jira_issue_id!r})"


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
