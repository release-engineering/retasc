# SPDX-License-Identifier: GPL-3.0-or-later
import re

import yaml
from pytest import mark, raises

from retasc.models.parse_rules import RuleParsingError, parse_rules

JIRA_TEMPLATES = [
    "main.yaml",
    "subtask1.yaml",
    "subtask2.yaml",
    "secondary.yaml",
]
RULE_DATA = {
    "version": 1,
    "name": "Example Rule",
    "prerequisites": [
        {"schedule_task": "TASK", "days_before_or_after": 5},
        {"rule": "Dependent Rule 1"},
        {"rule": "Dependent Rule 2"},
    ],
    "jira_issues": [
        {
            "id": "main",
            "template": "main.yaml",
            "subtasks": [
                {"id": "main1", "template": "subtask1.yaml"},
                {"id": "main2", "template": "subtask2.yaml"},
            ],
        },
        {"id": "secondary", "template": "secondary.yaml"},
    ],
}
DEPENDENT_RULES_DATA = [
    {
        "version": 1,
        "name": "Dependent Rule 1",
        "prerequisites": [
            {
                "schedule_task": "TASK",
                "days_before_or_after": -14,
            }
        ],
        "jira_issues": [],
    },
    {
        "version": 1,
        "name": "Dependent Rule 2",
        "prerequisites": [
            {
                "schedule_task": "TASK",
                "days_before_or_after": -7,
            }
        ],
        "jira_issues": [],
    },
]


def create_jira_templates(path):
    for template in JIRA_TEMPLATES:
        file = path / template
        file.write_text(yaml.dump({}, sort_keys=False))


def create_dependent_rules(rule_path):
    file = rule_path / "other_rules.yml"
    file.write_text(yaml.dump(DEPENDENT_RULES_DATA, sort_keys=False))


def test_parse_no_rules(rule_path):
    with raises(RuleParsingError, match="No rules found in '.*/rules'"):
        parse_rules(str(rule_path))


def test_parse_rule_valid_simple(rule_path):
    create_dependent_rules(rule_path)
    parse_rules(str(rule_path / "other_rules.yml"))


def test_parse_rule_valid(tmp_path, rule_path):
    file = rule_path / "rule.yaml"
    file.write_text(yaml.dump(RULE_DATA))
    create_dependent_rules(rule_path)
    create_jira_templates(tmp_path)
    parse_rules(str(rule_path), templates_path=tmp_path)


def test_parse_rule_invalid(invalid_rule_file):
    with raises(RuleParsingError):
        parse_rules(invalid_rule_file)


def test_parse_rule_missing_dependent_rules(tmp_path, rule_path):
    file = rule_path / "rule.yaml"
    file.write_text(yaml.dump(RULE_DATA))
    create_jira_templates(tmp_path)
    expected_error = re.escape(
        f"Invalid rule 'Example Rule' (file {str(file)!r}):"
        "\n  Dependent rule do not exist: 'Dependent Rule 1'"
        "\n  Dependent rule do not exist: 'Dependent Rule 2'"
    )
    with raises(RuleParsingError, match=expected_error):
        parse_rules(str(rule_path), templates_path=tmp_path)


def test_parse_rule_missing_jira_templates(rule_path, tmp_path):
    file = rule_path / "rule.yaml"
    file.write_text(yaml.dump(RULE_DATA, sort_keys=False))
    create_dependent_rules(rule_path)
    expected_error = (
        re.escape(
            f"Invalid rule 'Example Rule' (file {str(file)!r}):"
            "\n  Jira issue template files not found: "
        )
        + "[^\n]*"
        + re.escape(repr(str(tmp_path / "main.yaml")))
    )
    with raises(RuleParsingError, match=expected_error):
        parse_rules(str(rule_path), templates_path=tmp_path)


def test_parse_rule_duplicate_name(rule_path, rule_dict):
    rule_dict["name"] = "DUPLICATE"
    for filename in ("rule1.yml", "rule2.yml"):
        file = rule_path / filename
        file.write_text(yaml.dump(rule_dict))

    expected_error = (
        "Duplicate rule name 'DUPLICATE' in files: '[^']*/rule1.yml', '[^']*/rule2.yml'"
    )
    with raises(RuleParsingError, match=expected_error):
        parse_rules(rule_path)


@mark.parametrize("content", ("TEST: [", "[].", "[[[]]"))
def test_parse_rule_ivalid_yaml(content, rule_path):
    file = rule_path / "rule.yaml"
    file.write_text(content)
    expected_error = re.escape(f"Invalid YAML file {str(file)!r}: ") + ".*"
    with raises(RuleParsingError, match=expected_error):
        parse_rules(str(rule_path))
