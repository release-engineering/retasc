# SPDX-License-Identifier: GPL-3.0-or-later
import os
from collections.abc import Iterator
from itertools import takewhile

import yaml
from pydantic import BaseModel, Field

from retasc.jira import JIRA_ISSUE_ID_LABEL_PREFIX, JIRA_LABEL
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.utils import to_comma_separated

from .base import PrerequisiteBase


def _is_resolved(issue: dict) -> bool:
    return issue["fields"]["resolution"] is not None


def _set_parent_issue(fields: dict, parent_issue_key: str | None = None):
    if parent_issue_key is not None:
        fields["parent"] = {"key": parent_issue_key}


def _edit_issue(issue, fields, context, parent_issue_key: str | None = None):
    to_update = {k: v for k, v in fields.items() if issue["fields"][k] != v}
    if not to_update:
        return

    context.report.set("update", to_update)
    _set_parent_issue(to_update, parent_issue_key)
    context.jira.edit_issue(issue["key"], to_update)


def _create_issue(fields, context, label: str, parent_issue_key: str | None = None):
    context.report.set("create", fields)
    _set_parent_issue(fields, parent_issue_key)
    fields.setdefault("labels", []).extend([JIRA_LABEL, label])
    issue = context.jira.create_issue(fields)
    context.report.set("issue", issue["key"])
    return issue


def _update_issue(
    jira_issue_id: str, template: str, context, parent_issue_key: str | None = None
) -> dict | None:
    """
    Create and updates Jira issue if needed.

    The issue is updated according to the template.

    If the issue does not exist and none of the preceding prerequisites are in
    Pending state, the issue is created.

    Returns the managed Jira issue or None if it does not exist yet.
    """
    label = f"{JIRA_ISSUE_ID_LABEL_PREFIX}{jira_issue_id}"
    issue = context.issues.pop(label, None)

    if issue:
        context.report.set("issue", issue["key"])
        if _is_resolved(issue):
            return issue

    with open(template) as f:
        template_content = f.read()

    content = context.template.render(template_content)
    fields = yaml.safe_load(content)

    if issue:
        _edit_issue(issue, fields, context, parent_issue_key=parent_issue_key)
        return issue

    if context.prerequisites_state > ReleaseRuleState.Pending:
        return _create_issue(
            fields, context, label=label, parent_issue_key=parent_issue_key
        )

    return None


class JiraIssueTemplate(BaseModel):
    id: str = Field(description="Unique identifier for the issue.")
    template: str = Field(description="Path to the Jira issue template YAML file")


class PrerequisiteJiraIssue(PrerequisiteBase):
    """
    Prerequisite Jira issue.

    The Jira issue is created when no preceding prerequisites are in Pending state.

    The existing Jira issue is updated until it is resolved.

    After the Jira issue is resolved the prerequisite state is Completed,
    otherwise InProgress if issue has been created or Pending if it does not
    exist yet.
    """

    jira_issue_id: str = Field(description="Unique identifier for the issue.")
    template: str = Field(description="Path to the Jira issue template YAML file")
    subtasks: list[JiraIssueTemplate] = Field(default_factory=list)

    def validation_errors(self, rules) -> list[str]:
        errors = []

        missing_files = {
            file for file in template_paths(self) if not os.path.isfile(file)
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
        """Return Completed only if all issues were resolved."""
        issue = _update_issue(self.jira_issue_id, self.template, context)

        if issue is None:
            return ReleaseRuleState.Pending

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
