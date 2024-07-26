import copy
import subprocess

import yaml

from retasc.validator.validate_rules import validate_rule, validate_rule_dict

valid_rule_dict = {
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

invalid_rule_dict = copy.deepcopy(valid_rule_dict)
invalid_rule_dict["prerequisites"]["days_before_or_after"] = "invalid_type"

valid_rule_yaml = yaml.dump(valid_rule_dict, sort_keys=False)


def test_validate_rule_dict_valid():
    assert validate_rule_dict(valid_rule_dict) is True


def test_validate_rule_dict_invalid():
    assert validate_rule_dict(invalid_rule_dict) is False


def test_validate_rule(tmp_path):
    rule_file = tmp_path / "example_rule.yaml"
    rule_file.write_text(valid_rule_yaml)
    assert validate_rule(str(rule_file)) is True


def test_validate_rule_script(tmp_path):
    rule_file = tmp_path / "example_rule.yaml"
    rule_file.write_text(valid_rule_yaml)
    result = subprocess.run(
        ["python", "src/retasc/validator/validate_rules.py", str(rule_file)],
        check=True,
    )
    assert result.returncode == 0
