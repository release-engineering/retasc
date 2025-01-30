# SPDX-License-Identifier: GPL-3.0-or-later
import json
import re
from datetime import UTC, date, datetime
from unittest.mock import ANY, Mock, call, patch

from pytest import fixture, mark, raises

from retasc.models.config import parse_config
from retasc.models.inputs.jira_issues import JiraIssues
from retasc.models.inputs.product_pages_releases import parse_version
from retasc.models.prerequisites.condition import PrerequisiteCondition
from retasc.models.prerequisites.rule import PrerequisiteRule
from retasc.models.prerequisites.schedule import PrerequisiteSchedule
from retasc.models.prerequisites.target_date import PrerequisiteTargetDate
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.product_pages_api import ProductPagesScheduleTask
from retasc.run import run

from .factory import Factory

DUMMY_ISSUE = """
summary: test
"""
INPUT = "ProductPagesRelease('rhel-10.0')"


def call_run(*, additional_jira_fields: dict = {}):
    config = parse_config("examples/config.yaml")
    config.jira_fields.update(additional_jira_fields)
    return run(config=config, jira_token="", dry_run=False)


def issue_labels(issue_id: str) -> list[str]:
    return [f"retasc-id-{issue_id}"]


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
    assert report.data == {INPUT: {"rule1": {"state": "Completed"}}}


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
    inputs = (
        "ProductPagesRelease('rhel-9.0')",
        INPUT,
    )
    assert report.data == {
        input: {
            rule_dependency.name: {
                "TEST": {"counter": i},
                "state": "Completed",
            },
            rule1.name: expected_rule_data,
            rule2.name: expected_rule_data,
        }
        for i, input in enumerate(inputs, start=1)
    }
    assert len(condition_prereq.update_state.mock_calls) == 2


def test_run_rule_jira_issue_create(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    report = call_run()
    assert report.data == {
        INPUT: {
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
    mock_jira.create_issue.assert_called_once_with(
        {
            "summary": "test",
            "labels": issue_labels(jira_issue_prereq.jira_issue_id),
        }
    )


def test_run_rule_jira_search_once_per_prerequisite(factory, mock_jira, mock_pp):
    releases = ["rhel-10.0", "rhel-9.9"]
    mock_pp.active_releases.return_value = releases
    jira_issue_prereq = factory.new_jira_issue_prerequisite(
        DUMMY_ISSUE, jira_issue_id="test-{{ release }}"
    )
    rules = [factory.new_rule(prerequisites=[jira_issue_prereq]) for _ in range(2)]
    report = call_run()
    assert report.data == {
        f"ProductPagesRelease('{release}')": {
            rule.name: {
                f"Jira('test-{release}')": {
                    "create": '{"summary": "test"}',
                    "issue": ANY,
                    "state": "InProgress",
                },
                "state": "InProgress",
            }
            for rule in rules
        }
        for release in releases
    }
    assert mock_jira.search_issues.mock_calls == [
        call(
            jql=f'labels="retasc-id-test-{release}"',
            fields=["labels", "resolution", "summary"],
        )
        for release in releases
        for _ in range(2)
    ]


def test_run_rule_jira_search_once_per_jql(factory, mock_jira):
    issue_ids = ["TICKET-1", "TICKET-2"]
    mock_jira.search_issues.return_value = [
        {
            "key": issue_id,
            "fields": {
                "labels": ["test-label"],
                "description": f"This is {issue_id}",
            },
        }
        for issue_id in issue_ids
    ]
    jql = "labels=test-label"
    input = JiraIssues(jql=jql, fields=["description"])
    condition = "[jira_issue.key, jira_issue.fields.description]"
    condition_prereq = PrerequisiteCondition(condition=condition)
    rules = [
        factory.new_rule(inputs=[input], prerequisites=[condition_prereq])
        for _ in range(2)
    ]
    report = call_run()
    assert report.data == {
        f"JiraIssues('{issue_id}')": {
            rule.name: {
                f"Condition({condition!r})": {
                    "result": [f"{issue_id}", f"This is {issue_id}"],
                },
                "state": "Completed",
            }
            for rule in rules
        }
        for issue_id in issue_ids
    }
    assert mock_jira.search_issues.mock_calls == [call(jql=jql, fields=["description"])]


def test_run_rule_jira_issue_create_subtasks(factory):
    subtasks = [
        factory.new_jira_subtask(DUMMY_ISSUE),
        factory.new_jira_subtask(DUMMY_ISSUE),
    ]
    jira_issue_prereq = factory.new_jira_issue_prerequisite(
        DUMMY_ISSUE, subtasks=subtasks
    )
    condition = "jira_issues | default([]) | sort"
    condition_prereq = PrerequisiteCondition(condition=condition)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq, condition_prereq])
    report = call_run()
    assert report.data == {
        INPUT: {
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
        INPUT: {
            rule.name: {
                "Jira('test_jira_template_1')": {
                    "issue": "TEST-1",
                    "state": "InProgress",
                },
                "state": "InProgress",
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_not_called()


def test_run_rule_jira_issue_not_unique(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": f"TEST-{i}",
            "fields": {
                "labels": issue_labels(jira_issue_prereq.jira_issue_id),
                "resolution": None,
                "summary": "test",
            },
        }
        for i in [1, 2]
    ]

    expected_error = re.escape(
        "Found multiple issues with the same ID label 'retasc-id-test_jira_template_1': 'TEST-1', 'TEST-2'"
    )
    with raises(RuntimeError, match=expected_error):
        call_run()

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
        INPUT: {
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
        INPUT: {
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
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", {"labels": expected_labels})


def test_run_rule_jira_issue_update_complex_field(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite("""
        assignee: {key: alice}
    """)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    current_value = {"name": "Bob", "key": "bob"}
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "assignee": current_value,
                "labels": ["retasc-id-test_jira_template_1"],
                "resolution": None,
            },
        }
    ]
    expected_fields = {"assignee": {"key": "alice"}}
    report = call_run(additional_jira_fields={"assignee": "assignee"})
    assert report.data == {
        INPUT: {
            rule.name: {
                "Jira('test_jira_template_1')": {
                    "issue": "TEST-1",
                    "update": json.dumps(expected_fields),
                    "state": "InProgress",
                },
                "state": "InProgress",
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", expected_fields)

    current_value["key"] = "alice"
    current_value["name"] = "Alice"
    report = call_run(additional_jira_fields={"assignee": "assignee"})
    assert report.data == {
        INPUT: {
            rule.name: {
                "Jira('test_jira_template_1')": {
                    "issue": "TEST-1",
                    "state": "InProgress",
                },
                "state": "InProgress",
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once()


def test_run_rule_jira_issue_update_complex_nested_field(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite("""
        service:
          value: gating
          child:
            value: waiverdb
    """)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    current_value = {"value": "gating", "child": {"id": "123", "value": "greenwave"}}
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "customfield_123": current_value,
                "labels": ["retasc-id-test_jira_template_1"],
                "resolution": None,
            },
        }
    ]
    expected_fields = {
        "customfield_123": {"value": "gating", "child": {"value": "waiverdb"}}
    }
    additional_jira_fields = {"service": "customfield_123"}
    report = call_run(additional_jira_fields=additional_jira_fields)
    assert report.data == {
        INPUT: {
            rule.name: {
                "Jira('test_jira_template_1')": {
                    "issue": "TEST-1",
                    "update": json.dumps(expected_fields),
                    "state": "InProgress",
                },
                "state": "InProgress",
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", expected_fields)

    current_value["child"]["value"] = "waiverdb"
    report = call_run(additional_jira_fields=additional_jira_fields)
    assert report.data == {
        INPUT: {
            rule.name: {
                "Jira('test_jira_template_1')": {
                    "issue": "TEST-1",
                    "state": "InProgress",
                },
                "state": "InProgress",
            }
        }
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once()


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
        INPUT: {
            rule.name: {
                "Jira('test_jira_template_1')": {"issue": "TEST-1"},
                "state": "Completed",
            }
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
        INPUT: {
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


@mark.parametrize(
    ("target_date", "is_draft", "result"),
    (
        ("start_date", False, True),
        ("start_date", True, False),
        ("start_date - 1|weeks", False, True),
        ("start_date + 1|weeks", False, True),
        ("end_date - 1|weeks", False, True),
        ("end_date + 1|weeks", False, False),
        ("today", False, True),
        ("today", True, False),
        ("today + 1|days", False, False),
        ("today + 1|weeks", False, False),
    ),
)
def test_run_rule_schedule_target_date(target_date, is_draft, result, mock_pp, factory):
    mock_pp.release_schedules.return_value = {
        "TASK": ProductPagesScheduleTask(
            start_date=date(1990, 1, 1),
            end_date=datetime.now(UTC).date(),
            is_draft=is_draft,
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
    assert report.data[INPUT][rule.name]["state"] == state


def test_run_rule_schedule_missing(mock_pp, factory):
    mock_pp.release_schedules.return_value = {}
    rule = factory.new_rule(prerequisites=[PrerequisiteSchedule(schedule_task="TASK")])

    report = call_run()
    assert report.data[INPUT][rule.name] == {
        "Schedule('TASK')": {
            "state": "Pending",
            "pending_reason": "No schedule available yet",
        },
        "state": "Pending",
    }


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
    assert report.data[INPUT][rule.name]["state"] == state


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


def test_run_rule_jira_issue_input(factory, mock_jira):
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {},
        },
        {
            "key": "TEST-2",
            "fields": {},
        },
    ]
    condition = "jira_issue"
    condition_prereq = PrerequisiteCondition(condition=condition)
    rule = factory.new_rule(
        inputs=[JiraIssues(jql="labels=test-label", fields=[])],
        prerequisites=[condition_prereq],
    )
    report = call_run()
    assert report.data == {
        f"JiraIssues('TEST-{i}')": {
            rule.name: {
                f"Condition({condition!r})": {
                    "result": issue,
                },
                "state": "Completed",
            }
        }
        for i, issue in enumerate(mock_jira.search_issues.return_value, start=1)
    }
