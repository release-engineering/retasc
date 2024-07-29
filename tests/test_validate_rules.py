from copy import deepcopy

import pytest
import yaml

from retasc.validator.validate_rules import validate_rule, validate_rule_dict


@pytest.fixture
def valid_rule_dict():
    return {
        "version": 1,
        "name": "Example Rule",
        "prerequisites": {
            "pp_schedule_item_name": "Release Date",
            "days_before_or_after": 5,
            "dependent_rules": ["Dependent Rule 1", "Dependent Rule 2"],
        },
        "jira_issues": [
            {
                "template": "major_pre_beta/main.yaml",
                "subtasks": [
                    {"template": "major_pre_beta/subtasks/add_beta_repos.yaml"},
                    {"template": "major_pre_beta/subtasks/notify_team.yaml"},
                ],
            },
            {"template": "major_pre_beta/secondary.yaml"},
        ],
    }


def test_rule_dict_valid(valid_rule_dict):
    assert validate_rule_dict(valid_rule_dict) is True


def test_rule_valid(tmp_path, valid_rule_dict):
    rule_file = tmp_path / "example_rule.yaml"
    rule_file.write_text(yaml.dump(valid_rule_dict, sort_keys=False))
    assert validate_rule(str(rule_file)) is True


def test_invalid_incorrect_days_before_or_after_type(valid_rule_dict):
    invalid_rule_dict = deepcopy(valid_rule_dict)
    invalid_rule_dict["prerequisites"]["days_before_or_after"] = "invalid_type"
    assert validate_rule_dict(invalid_rule_dict) is False


# By default, additional fields are ignored by pydantic
def test_unexpected_fields(valid_rule_dict):
    invalid_rule = deepcopy(valid_rule_dict)
    invalid_rule["unexpected_field"] = "unexpected_value"
    assert validate_rule_dict(invalid_rule) is True


def test_incorrect_version_types(valid_rule_dict):
    invalid_rule = deepcopy(valid_rule_dict)
    invalid_rule["version"] = "one"
    assert validate_rule_dict(invalid_rule) is False


def test_missing_fields():
    invalid_rule = {
        "name": "Example Rule",
    }
    assert validate_rule_dict(invalid_rule) is False
