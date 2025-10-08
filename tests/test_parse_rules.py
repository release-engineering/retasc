# SPDX-License-Identifier: GPL-3.0-or-later
import re

from pytest import fixture, mark, raises

from retasc.models.config import parse_config
from retasc.models.parse_rules import RuleParsingError, parse_rules
from retasc.yaml import yaml

JIRA_TEMPLATES = [
    "main.yaml",
    "subtask1.yaml",
    "subtask2.yaml",
    "secondary.yaml",
]
RULE_DATA = {
    "name": "Example Rule",
    "prerequisites": [
        {"schedule_task": "TASK"},
        {"condition": "today >= start_date + 5|days"},
        {"rule": "Dependent Rule 1"},
        {"rule": "Dependent Rule 2"},
        {
            "jira_issue": "main",
            "template": "main.yaml",
            "subtasks": [
                {"jira_issue": "main1", "template": "subtask1.yaml"},
                {"jira_issue": "main2", "template": "subtask2.yaml"},
            ],
        },
        {"jira_issue": "secondary", "template": "secondary.yaml"},
    ],
}
DEPENDENT_RULES_DATA = [
    {
        "name": "Dependent Rule 1",
        "prerequisites": [
            {"schedule_task": "TASK"},
            {"condition": "today >= start_date - 2|weeks"},
        ],
    },
    {
        "name": "Dependent Rule 2",
        "prerequisites": [
            {"schedule_task": "TASK"},
            {"condition": "today >= start_date - 1|week"},
        ],
    },
]


def call_parse_rules(path):
    config = parse_config("examples/config.yaml")
    return parse_rules(path, config)


@fixture
def templates_root(tmp_path, monkeypatch):
    monkeypatch.setenv("RETASC_JIRA_TEMPLATES_ROOT", str(tmp_path))
    yield tmp_path


def create_jira_templates(path):
    for template in JIRA_TEMPLATES:
        file = path / template
        yaml().dump({}, file)


def create_dependent_rules(rule_path):
    file = rule_path / "other_rules.yml"
    yaml().dump(DEPENDENT_RULES_DATA, file)


def test_parse_no_rules(rule_path):
    with raises(RuleParsingError, match="No rules found in '.*/rules'"):
        call_parse_rules(str(rule_path))


def test_parse_rule_valid_simple(rule_path):
    create_dependent_rules(rule_path)
    call_parse_rules(str(rule_path / "other_rules.yml"))


def test_parse_rule_valid(templates_root, rule_path):
    file = rule_path / "rule.yaml"
    yaml().dump(RULE_DATA, file)
    create_dependent_rules(rule_path)
    create_jira_templates(templates_root)
    call_parse_rules(str(rule_path))


def test_parse_rule_invalid(invalid_rule_file):
    with raises(RuleParsingError):
        call_parse_rules(invalid_rule_file)


def test_parse_rule_missing_dependent_rules(templates_root, rule_path):
    file = rule_path / "rule.yaml"
    yaml().dump(RULE_DATA, file)
    create_jira_templates(templates_root)
    expected_error = re.escape(
        f"Invalid rule 'Example Rule' (file {str(file)!r}):"
        "\n  Dependent rule does not exist: 'Dependent Rule 1'"
        "\n  Dependent rule does not exist: 'Dependent Rule 2'"
    )
    with raises(RuleParsingError, match=expected_error):
        call_parse_rules(str(rule_path))


def test_parse_rule_missing_jira_templates(rule_path, templates_root):
    file = rule_path / "rule.yaml"
    yaml().dump(RULE_DATA, file)
    create_dependent_rules(rule_path)
    expected_error = (
        re.escape(
            f"Invalid rule 'Example Rule' (file {str(file)!r}):"
            "\n  Jira issue template files not found: "
        )
        + "[^\n]*"
        + re.escape(repr(str(templates_root / "main.yaml")))
    )
    with raises(RuleParsingError, match=expected_error):
        call_parse_rules(str(rule_path))


def test_parse_rule_duplicate_jira_ids(rule_path, templates_root):
    file = rule_path / "rule.yaml"
    rule2 = {
        "name": "Example Rule 2",
        "prerequisites": [
            {
                "jira_issue": "main",
                "template": "main.yaml",
                "subtasks": [
                    {"jira_issue": "main1", "template": "subtask1.yaml"},
                ],
            },
            {"jira_issue": "secondary", "template": "secondary.yaml"},
        ],
    }
    rules_data = [RULE_DATA, rule2]
    yaml().dump(rules_data, file)
    create_dependent_rules(rule_path)
    create_jira_templates(templates_root)
    expected_error = re.escape(
        f"Invalid rule 'Example Rule 2' (file {str(file)!r}):"
        "\n  Jira issue ID(s) already used elsewhere: 'main', 'main1'"
        "\n  Jira issue ID(s) already used elsewhere: 'secondary'"
    )
    with raises(RuleParsingError, match=expected_error):
        call_parse_rules(str(rule_path))


def test_parse_rule_duplicate_name(rule_path, rule_dict):
    rule_dict["name"] = "DUPLICATE"
    for filename in ("rule1.yml", "rule2.yml"):
        file = rule_path / filename
        yaml().dump(rule_dict, file)

    expected_error = (
        "Duplicate rule name 'DUPLICATE' in files: '[^']*/rule1.yml', '[^']*/rule2.yml'"
    )
    with raises(RuleParsingError, match=expected_error):
        call_parse_rules(rule_path)


@mark.parametrize("content", ("TEST: [", "[].", "[[[]]"))
def test_parse_rule_ivalid_yaml(content, rule_path):
    file = rule_path / "rule.yaml"
    file.write_text(content)
    expected_error = re.escape(f"Invalid YAML file {str(file)!r}: ") + ".*"
    with raises(RuleParsingError, match=expected_error):
        call_parse_rules(str(rule_path))
