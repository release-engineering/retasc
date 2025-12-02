# SPDX-License-Identifier: GPL-3.0-or-later
from textwrap import dedent
from typing import Any

from retasc.models.prerequisites.jira_issue import (
    JiraIssueTemplate,
    PrerequisiteJiraIssue,
)
from retasc.models.rule import Rule


class Factory:
    last_rule_id: int = 0
    last_jira_issue_number: int = 0

    def __init__(self, tmpdir, rules_dict):
        self.tmpdir = tmpdir
        self.rules_dict = rules_dict

    def new_rule(self, *, name=None, prerequisites=None, **kwargs):
        if name is None:
            self.last_rule_id += 1
            name = f"test_rule_{self.last_rule_id}"

        if prerequisites is None:
            prerequisites = []

        rule = Rule(
            name=name,
            prerequisites=prerequisites,
            **kwargs,
        )
        self.rules_dict[name] = rule
        return rule

    def add_rule(self, rule: Rule):
        self.rules_dict[rule.name] = rule

    def new_jira_issue_id(self) -> str:
        self.last_jira_issue_number += 1
        return f"test_jira_template_{self.last_jira_issue_number}"

    def new_jira_template_file(self, jira_issue: str, template: str) -> str:
        tmp = self.tmpdir / f"jira_template_{jira_issue}.yml"
        with open(tmp, "w") as f:
            f.write(dedent(template))

        return str(tmp)

    def new_jira_subtask(self, template: str) -> JiraIssueTemplate:
        jira_issue = self.new_jira_issue_id()
        file = self.new_jira_template_file(jira_issue, template)
        return JiraIssueTemplate(jira_issue=jira_issue, template=file)

    def new_jira_issue_prerequisite(
        self,
        template: str | None = None,
        *,
        fields: dict[str, Any] | None = None,
        jira_issue: str = "",
        subtasks=[],
    ):
        jira_issue_ = jira_issue or self.new_jira_issue_id()

        if template is None:
            file = None
        else:
            file = self.new_jira_template_file(jira_issue_, template)

        return PrerequisiteJiraIssue(
            jira_issue=jira_issue_,
            template=file,
            fields=fields or {},
            subtasks=subtasks,
        )
