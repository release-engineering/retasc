# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy

import pytest
import yaml


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


@pytest.fixture
def valid_rule_file(tmp_path, valid_rule_dict):
    rule_file = tmp_path / "valid_rule.yaml"
    rule_file.write_text(yaml.dump(valid_rule_dict, sort_keys=False))
    return str(rule_file)


@pytest.fixture
def generic_invalid_rule_file(tmp_path, valid_rule_dict):
    invalid_rule_dict = deepcopy(valid_rule_dict)
    del invalid_rule_dict["version"]
    rule_file = tmp_path / "invalid_rule.yaml"
    rule_file.write_text(yaml.dump(invalid_rule_dict, sort_keys=False))
    return str(rule_file)
