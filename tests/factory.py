# SPDX-License-Identifier: GPL-3.0-or-later
from textwrap import dedent

from retasc.models.prerequisites.jira_issue import PrerequisiteJiraIssue
from retasc.models.rule import Rule


class Factory:
    last_rule_id: int = 0
    last_jira_template_id: int = 0

    def __init__(self, tmpdir, rules_dict):
        self.tmpdir = tmpdir
        self.rules_dict = rules_dict

    def new_rule(self, *, name=None, version=1, prerequisites=[], **kwargs):
        if name is None:
            self.last_rule_id += 1
            name = f"test_rule_{self.last_rule_id}"

        rule = Rule(
            version=version,
            name=name,
            prerequisites=prerequisites,
            **kwargs,
        )
        self.rules_dict[name] = rule
        return rule

    def new_jira_issue_prerequisite(self, template, *, subtasks=[]):
        self.last_jira_template_id += 1
        jira_issue_id = f"test_jira_template_{self.last_jira_template_id}"

        tmp = self.tmpdir / f"jira_template_{jira_issue_id}.yml"
        with open(tmp, "w") as f:
            f.write(dedent(template))

        return PrerequisiteJiraIssue(
            jira_issue_id=jira_issue_id, template=str(tmp), subtasks=subtasks
        )
