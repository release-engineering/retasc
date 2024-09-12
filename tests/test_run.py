# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import UTC, date, datetime
from unittest.mock import patch

from pytest import fixture, mark

from retasc.jira import JIRA_ISSUE_ID_LABEL_PREFIX, JIRA_LABEL
from retasc.models.prerequisites.condition import PrerequisiteCondition
from retasc.models.prerequisites.schedule import PrerequisiteSchedule
from retasc.models.prerequisites.target_date import PrerequisiteTargetDate
from retasc.product_pages_api import ProductPagesScheduleTask
from retasc.run import parse_version, run

from .factory import Factory

DUMMY_ISSUE = """
summary: test
"""


@fixture
def mock_parse_rules():
    with patch("retasc.run.parse_rules") as mock:
        mock.return_value = {}
        yield mock


@fixture
def factory(tmpdir, mock_parse_rules):
    return Factory(tmpdir, mock_parse_rules.return_value)


def test_parse_version():
    assert parse_version("rhel") == (0, 0)
    assert parse_version("rhel-1-2") == (1, 2)
    assert parse_version("rhel-1.2") == (1, 2)
    assert parse_version("rhel-6-els") == (6, 0)


def test_run_rule_simple(factory):
    factory.new_rule(name="rule1")
    report = run(dry_run=False)
    assert report.data == {"rhel": {"rhel-10.0": {"rule1": {"state": "Completed"}}}}


def test_run_rule_jira_issue_create(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    report = run(dry_run=False)
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_1')": {
                        "create": {"summary": "test"},
                        "issue": "TEST",
                        "state": "InProgress",
                    },
                    "state": "InProgress",
                }
            }
        }
    }
    mock_jira.create_issue.assert_called_once_with(
        {
            "summary": "test",
            "labels": [JIRA_LABEL, f"{JIRA_ISSUE_ID_LABEL_PREFIX}test_jira_template_1"],
        }
    )


def test_run_rule_jira_issue_in_progress(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "labels": ["retasc-id-test_jira_template_1"],
                "resolution": None,
                "summary": "test",
            },
        }
    ]
    report = run(dry_run=False)
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_1')": {
                        "issue": "TEST-1",
                        "state": "InProgress",
                    },
                    "state": "InProgress",
                }
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_not_called()


def test_run_rule_jira_issue_in_progress_update(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "labels": ["retasc-id-test_jira_template_1"],
                "resolution": None,
                "summary": "test old",
            },
        }
    ]
    report = run(dry_run=False)
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_1')": {
                        "issue": "TEST-1",
                        "update": {"summary": "test"},
                        "state": "InProgress",
                    },
                    "state": "InProgress",
                }
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", {"summary": "test"})


def test_run_rule_jira_issue_completed(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "labels": ["retasc-id-test_jira_template_1"],
                "resolution": "Closed",
            },
        }
    ]
    report = run(dry_run=False)
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_1')": {"issue": "TEST-1"},
                    "state": "Completed",
                }
            }
        }
    }


def test_run_rule_jira_issue_drop(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "labels": ["retasc-managed", "retasc-id-test_jira_template_1"],
                "summary": "test",
                "resolution": None,
            },
        },
        {
            "key": "TEST-2",
            "fields": {
                "labels": ["retasc-managed", "retasc-id-test_jira_template_2"],
                "resolution": None,
            },
        },
        {
            "key": "TEST-3",
            "fields": {
                "labels": ["retasc-managed"],
                "resolution": None,
            },
        },
        {
            "key": "TEST-4",
            "fields": {
                "labels": ["retasc-managed"],
                "resolution": "Closed",
            },
        },
    ]
    report = run(dry_run=False)
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_1')": {
                        "issue": "TEST-1",
                        "state": "InProgress",
                    },
                    "state": "InProgress",
                },
                "dropped_issues": ["TEST-2", "TEST-3"],
            },
        }
    }


@mark.parametrize(
    ("condition_expr", "result"),
    (
        ("true", True),
        ("major >= 10", True),
        ("false", False),
        ("major < 10", False),
    ),
)
def test_run_rule_condition_failed(condition_expr, result, factory):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    condition = PrerequisiteCondition(condition=condition_expr)
    rule = factory.new_rule(prerequisites=[condition, jira_issue_prereq])

    # A Jira issues are created/updated only if none of the preceding
    # prerequisites are Pending (all preceding conditions must pass).
    if result:
        issue_prereq = {
            "create": {"summary": "test"},
            "issue": "TEST",
            "state": "InProgress",
        }
    else:
        issue_prereq = {"state": "Pending"}

    report = run(dry_run=False)
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    f"Condition({condition_expr!r})": {
                        "result": result,
                        **({} if result else {"state": "Pending"}),
                    },
                    "Jira('test_jira_template_1')": issue_prereq,
                    "state": "InProgress" if result else "Pending",
                }
            }
        }
    }


@mark.parametrize(
    ("target_date", "result"),
    (
        ("start_date", True),
        ("start_date - 1|weeks", True),
        ("start_date + 1|weeks", True),
        ("end_date - 1|weeks", True),
        ("end_date + 1|weeks", False),
        ("today", True),
        ("today + 1|days", False),
        ("today + 1|weeks", False),
    ),
)
def test_run_rule_schedule_target_date(target_date, result, mock_pp, factory):
    mock_pp.release_schedules.return_value = {
        "TASK": ProductPagesScheduleTask(
            start_date=date(1990, 1, 1),
            end_date=datetime.now(UTC).date(),
        ),
    }
    rule = factory.new_rule(
        prerequisites=[
            PrerequisiteSchedule(schedule_task="TASK"),
            PrerequisiteTargetDate(target_date=target_date),
        ]
    )

    state = "Completed" if result else "Pending"
    report = run(dry_run=False)
    assert report.data["rhel"]["rhel-10.0"][rule.name]["state"] == state


@mark.parametrize(
    ("condition_expr", "result"),
    (
        ("start_date | string == '1990-01-01'", True),
        ("start_date | string != '1990-01-01'", False),
        ("(start_date +31|days) | string == '1990-02-01'", True),
        ("(start_date +1|weeks) | string == '1990-01-08'", True),
        ("(start_date +1|weeks) | string == '1990-01-08'", True),
        ("today.year >= 2024", True),
        ("start_date.weekday() == MONDAY", True),
    ),
)
def test_run_rule_schedule_params(condition_expr, result, mock_pp, factory):
    mock_pp.release_schedules.return_value = {
        "TASK": ProductPagesScheduleTask(
            start_date=date(1990, 1, 1),
            end_date=date(1990, 1, 3),
        ),
    }
    schedule = PrerequisiteSchedule(schedule_task="TASK")
    condition = PrerequisiteCondition(condition=condition_expr)
    rule = factory.new_rule(prerequisites=[schedule, condition])

    state = "Completed" if result else "Pending"
    report = run(dry_run=False)
    assert report.data["rhel"]["rhel-10.0"][rule.name]["state"] == state
