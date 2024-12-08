# SPDX-License-Identifier: GPL-3.0-or-later
import json
from datetime import UTC, date, datetime
from unittest.mock import Mock, patch

from pytest import fixture, mark, raises

from retasc.models.config import parse_config
from retasc.models.prerequisites.condition import PrerequisiteCondition
from retasc.models.prerequisites.rule import PrerequisiteRule
from retasc.models.prerequisites.schedule import PrerequisiteSchedule
from retasc.models.prerequisites.target_date import PrerequisiteTargetDate
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.product_pages_api import ProductPagesScheduleTask
from retasc.run import parse_version, run

from .factory import Factory

DUMMY_ISSUE = """
summary: test
"""


def call_run():
    config = parse_config("examples/config.yaml")
    return run(config=config, jira_token="", dry_run=False)


def issue_labels(issue_id: str) -> list[str]:
    return [f"retasc-id-{issue_id}", "retasc-managed", "retasc-release-rhel-10.0"]


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
    report = call_run()
    assert report.data == {"rhel": {"rhel-10.0": {"rule1": {"state": "Completed"}}}}


def test_run_rule_update_state_once(factory, mock_pp):
    """
    Rule.update_state() is called exactly once (cached for later) for each
    release.
    """
    releases = ["rhel-9.0", "rhel-10.0"]
    mock_pp.active_releases.return_value = releases

    condition_prereq = Mock(spec=PrerequisiteCondition)

    counter = 0

    def mock_update_state(context):
        nonlocal counter
        counter += 1
        context.template.params["counter"] = counter
        context.report.set("counter", counter)
        return ReleaseRuleState.Completed

    condition_prereq.update_state.side_effect = mock_update_state
    condition_prereq.section_name.return_value = "TEST"

    rule_dependency = factory.new_rule(prerequisites=[condition_prereq])
    rule1 = factory.new_rule(
        prerequisites=[PrerequisiteRule(rule=rule_dependency.name)]
    )
    rule2 = factory.new_rule(
        prerequisites=[PrerequisiteRule(rule=rule_dependency.name)]
    )
    report = call_run()
    expected_rule_data = {
        f"Rule({rule_dependency.name!r})": {},
        "state": "Completed",
    }
    assert report.data == {
        "rhel": {
            release: {
                rule_dependency.name: {
                    "TEST": {"counter": i},
                    "state": "Completed",
                },
                rule1.name: expected_rule_data,
                rule2.name: expected_rule_data,
            }
            for i, release in enumerate(releases, start=1)
        }
    }
    assert len(condition_prereq.update_state.mock_calls) == 2


def test_run_rule_jira_issue_create(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    report = call_run()
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_1')": {
                        "create": '{"summary": "test"}',
                        "issue": "TEST-1",
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
            "labels": issue_labels(jira_issue_prereq.jira_issue_id),
        }
    )


def test_run_rule_jira_issue_create_subtasks(factory, mock_jira):
    subtasks = [
        factory.new_jira_subtask(DUMMY_ISSUE),
        factory.new_jira_subtask(DUMMY_ISSUE),
    ]
    jira_issue_prereq = factory.new_jira_issue_prerequisite(
        DUMMY_ISSUE, subtasks=subtasks
    )
    condition = "issues | sort"
    condition_prereq = PrerequisiteCondition(condition=condition)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq, condition_prereq])
    report = call_run()
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_3')": {
                        "create": '{"summary": "test"}',
                        "issue": "TEST-1",
                        "state": "InProgress",
                        "Subtask('test_jira_template_1')": {
                            "create": '{"summary": "test"}',
                            "issue": "TEST-2",
                        },
                        "Subtask('test_jira_template_2')": {
                            "create": '{"summary": "test"}',
                            "issue": "TEST-3",
                        },
                    },
                    f"Condition({condition!r})": {
                        "result": [
                            "test_jira_template_1",
                            "test_jira_template_2",
                            "test_jira_template_3",
                        ],
                    },
                    "state": "InProgress",
                }
            }
        }
    }


def test_run_rule_jira_issue_in_progress(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "labels": issue_labels(jira_issue_prereq.jira_issue_id),
                "resolution": None,
                "summary": "test",
            },
        }
    ]
    report = call_run()
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
                "labels": issue_labels(jira_issue_prereq.jira_issue_id),
                "resolution": None,
                "summary": "test old",
            },
        }
    ]
    report = call_run()
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_1')": {
                        "issue": "TEST-1",
                        "update": '{"summary": "test"}',
                        "state": "InProgress",
                    },
                    "state": "InProgress",
                }
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", {"summary": "test"})


def test_run_rule_jira_issue_update_labels(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite("""
        labels: [test1, test3]
    """)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    old_labels = issue_labels(jira_issue_prereq.jira_issue_id) + ["test1", "test2"]
    expected_labels = issue_labels(jira_issue_prereq.jira_issue_id) + ["test1", "test3"]
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "labels": old_labels,
                "resolution": None,
                "summary": "test old",
            },
        }
    ]
    report = call_run()
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    "Jira('test_jira_template_1')": {
                        "issue": "TEST-1",
                        "update": json.dumps({"labels": expected_labels}),
                        "state": "InProgress",
                    },
                    "state": "InProgress",
                }
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", {"labels": expected_labels})


def test_run_rule_jira_issue_completed(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "labels": issue_labels(jira_issue_prereq.jira_issue_id),
                "resolution": "Closed",
            },
        }
    ]
    report = call_run()
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
                "labels": issue_labels(jira_issue_prereq.jira_issue_id),
                "summary": "test",
                "resolution": None,
            },
        },
        {
            "key": "TEST-2",
            "fields": {
                "labels": issue_labels("test_jira_template_2"),
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
    report = call_run()
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
            "Jira('test_jira_template_1')": {
                "create": '{"summary": "test"}',
                "issue": "TEST-1",
                "state": "InProgress",
            }
        }
    else:
        issue_prereq = {}

    report = call_run()
    assert report.data == {
        "rhel": {
            "rhel-10.0": {
                rule.name: {
                    f"Condition({condition_expr!r})": {
                        "result": result,
                        **({} if result else {"state": "Pending"}),
                    },
                    **issue_prereq,
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
    report = call_run()
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
    report = call_run()
    assert report.data["rhel"]["rhel-10.0"][rule.name]["state"] == state


def test_run_rule_jira_issue_unsupported_fields(factory):
    jira_issue_prereq = factory.new_jira_issue_prerequisite("field_1: 1\nfield_2: 2\n")
    factory.new_rule(prerequisites=[jira_issue_prereq])
    expected_error = (
        f"Jira template {jira_issue_prereq.template!r} contains"
        " unsupported fields: 'field_1', 'field_2'"
        "\nSupported fields: 'description', 'labels', 'project', 'summary'"
    )
    with raises(RuntimeError, match=expected_error):
        call_run()


def test_run_rule_jira_issue_reserved_labels(factory):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(
        "labels: [retasc-id-test1, retasc-id-test2]"
    )
    factory.new_rule(prerequisites=[jira_issue_prereq])
    expected_error = (
        f"Jira template {jira_issue_prereq.template!r} must not use labels"
        " prefixed with 'retasc-id-': 'retasc-id-test1', 'retasc-id-test2'"
    )
    with raises(RuntimeError, match=expected_error):
        call_run()
