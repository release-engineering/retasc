# SPDX-License-Identifier: GPL-3.0-or-later
from textwrap import dedent

from retasc.models.jira_issue import JiraIssueTemplate
from retasc.models.rule import Rule


class Factory:
    last_rule_id: int = 0
    last_jira_template_id: int = 0

    def __init__(self, tmpdir):
        self.tmpdir = tmpdir

    def new_rule(
        self, *, name=None, version=1, prerequisites=[], jira_issues=[], **kwargs
    ):
        if name is None:
            self.last_rule_id += 1
            name = f"test_rule_{self.last_rule_id}"

        return Rule(
            version=version,
            name=name,
            prerequisites=prerequisites,
            jira_issues=jira_issues,
            **kwargs,
        )

    def new_jira_template(self, template, *, subtasks=[]):
        self.last_jira_template_id += 1
        id = f"test_jira_template_{self.last_jira_template_id}"

        tmp = self.tmpdir / f"jira_template_{id}.yml"
        with open(tmp, "w") as f:
            f.write(dedent(template))

        return JiraIssueTemplate(id=id, template=template, subtasks=subtasks)
