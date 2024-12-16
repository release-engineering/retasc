# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date
from unittest.mock import ANY, patch

from pytest import fixture

from retasc.product_pages_api import ProductPagesScheduleTask
from retasc.yaml import yaml


@fixture
def rule_dict():
    return {
        "version": 1,
        "name": "Example Rule",
        "inputs": [{"product": "rhel"}],
        "prerequisites": [
            {"schedule_task": "GA for rhel {{ major }}.{{ minor }}"},
            {"condition": "today >= start_date + 5|days"},
        ],
    }


@fixture
def rule_path(tmp_path):
    path = tmp_path / "rules"
    path.mkdir()
    yield path


@fixture
def valid_rule_file(rule_path, rule_dict):
    file = rule_path / "rule.yaml"
    yaml().dump(rule_dict, file)
    yield str(file)


@fixture
def invalid_rule_file(rule_path, rule_dict):
    del rule_dict["version"]
    file = rule_path / "rule.yaml"
    yaml().dump(rule_dict, file)
    yield str(file)


@fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("RETASC_CONFIG", "examples/config.yaml")
    monkeypatch.setenv("RETASC_JIRA_TOKEN", "")


def mock_jira_cls(cls: str, new_issue_key_prefix: str):
    with patch(cls, autospec=True) as mock_cls:
        mock = mock_cls(ANY, token=ANY, session=ANY)
        mock.search_issues.return_value = []

        last_issue_id = 0

        def mock_create_issue(fields):
            nonlocal last_issue_id
            last_issue_id += 1
            key = f"{new_issue_key_prefix}-{last_issue_id}"
            return {"key": key, "fields": {"resolution": None, **fields}}

        mock.create_issue.side_effect = mock_create_issue
        yield mock


@fixture(autouse=True)
def mock_jira():
    yield from mock_jira_cls("retasc.run.JiraClient", "TEST")


@fixture(autouse=True)
def mock_dryrun_jira():
    yield from mock_jira_cls("retasc.run.DryRunJiraClient", "DRYRUN")


@fixture(autouse=True)
def mock_pp():
    with patch("retasc.run.ProductPagesApi", autospec=True) as mock_cls:
        mock = mock_cls(ANY, session=ANY)
        mock.active_releases.return_value = ["rhel-10.0"]
        mock.release_schedules.return_value = {
            "GA for rhel 10.0": ProductPagesScheduleTask(
                start_date=date(1990, 1, 1),
                end_date=date(1990, 1, 2),
            ),
            "TASK": ProductPagesScheduleTask(
                start_date=date(1990, 1, 3),
                end_date=date(1990, 1, 4),
            ),
        }
        yield mock
