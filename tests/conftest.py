# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
import yaml


@pytest.fixture
def rule_dict():
    return {
        "version": 1,
        "name": "Example Rule",
        "prerequisites": {
            "pp_schedule_item_name": "Release Date",
            "days_before_or_after": 5,
        },
        "jira_issues": [],
    }


@pytest.fixture
def rule_path(tmp_path):
    path = tmp_path / "rules"
    path.mkdir()
    yield path


@pytest.fixture
def valid_rule_file(rule_path, rule_dict):
    file = rule_path / "rule.yaml"
    file.write_text(yaml.dump(rule_dict, sort_keys=False))
    yield str(file)


@pytest.fixture
def invalid_rule_file(rule_path, rule_dict):
    del rule_dict["version"]
    file = rule_path / "rule.yaml"
    file.write_text(yaml.dump(rule_dict, sort_keys=False))
    yield str(file)
