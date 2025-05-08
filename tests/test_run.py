# SPDX-License-Identifier: GPL-3.0-or-later
import json
from datetime import UTC, date, datetime
from textwrap import dedent
from unittest.mock import ANY, Mock, call, patch

from pytest import fixture, mark

from retasc.models.config import parse_config
from retasc.models.inputs.jira_issues import JiraIssues
from retasc.models.inputs.product_pages_releases import parse_version
from retasc.models.prerequisites.condition import PrerequisiteCondition
from retasc.models.prerequisites.rule import PrerequisiteRule
from retasc.models.prerequisites.schedule import PrerequisiteSchedule
from retasc.models.prerequisites.target_date import PrerequisiteTargetDate
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.models.rule import Rule
from retasc.product_pages_api import ProductPagesScheduleTask
from retasc.run import run

from .factory import Factory

DUMMY_ISSUE = """
summary: test
"""
DUMMY_ISSUE_FIELDS = {"summary": "test"}
INPUT = "ProductPagesReleases('rhel-10.0')"


def call_run(*, additional_jira_fields: dict = {}):
    config = parse_config("examples/config.yaml")
    config.jira_fields.update(additional_jira_fields)
    return run(config=config, jira_token="")


def issue_labels(issue_id: str) -> list[str]:
    return [f"retasc-id-{issue_id}-rhel-10.0"]


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
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [{"rule": "rule1", "state": "Completed"}],
            }
        ]
    }


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
    condition_prereq.model_dump.return_value = {"condition": "true"}

    rule_dependency = factory.new_rule(prerequisites=[condition_prereq])
    rule1 = factory.new_rule(
        prerequisites=[PrerequisiteRule(rule=rule_dependency.name)]
    )
    rule2 = factory.new_rule(
        prerequisites=[PrerequisiteRule(rule=rule_dependency.name)]
    )
    report = call_run()
    inputs = ("rhel-9.0", "rhel-10.0")
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": input,
                "rules": [
                    {
                        "rule": rule_dependency.name,
                        "state": "Completed",
                        "prerequisites": [{"type": "Mock", "counter": i}],
                    },
                    {
                        "rule": rule1.name,
                        "state": "Completed",
                        "prerequisites": [
                            {
                                "rule": rule_dependency.name,
                                "type": "Rule",
                            },
                        ],
                    },
                    {
                        "rule": rule2.name,
                        "state": "Completed",
                        "prerequisites": [
                            {
                                "rule": rule_dependency.name,
                                "type": "Rule",
                            },
                        ],
                    },
                ],
            }
            for i, input in enumerate(inputs, start=1)
        ]
    }
    assert len(condition_prereq.update_state.mock_calls) == 2


def test_run_rule_jira_issue_create(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "create": '{"summary": "test", "labels": ["retasc-id-test_jira_template_1-rhel-10.0"]}',
                                "issue_id": "TEST-1",
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
    }
    mock_jira.create_issue.assert_called_once_with(
        {
            "summary": "test",
            "labels": issue_labels(jira_issue_prereq.jira_issue),
        }
    )


def test_run_rule_jira_issue_fields(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(fields=DUMMY_ISSUE_FIELDS)
    factory.new_rule(prerequisites=[jira_issue_prereq])
    call_run()
    mock_jira.create_issue.assert_called_once_with(
        {
            "summary": "test",
            "labels": issue_labels(jira_issue_prereq.jira_issue),
        }
    )


def test_run_rule_jira_issue_fields_override_template(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(
        "{summary: TEST, test: value}", fields=DUMMY_ISSUE_FIELDS
    )
    factory.new_rule(prerequisites=[jira_issue_prereq])
    call_run()
    mock_jira.create_issue.assert_called_once_with(
        {
            "summary": "test",
            "test": "value",
            "labels": issue_labels(jira_issue_prereq.jira_issue),
        }
    )


def test_run_rule_jira_search_once_per_prerequisite(factory, mock_jira, mock_pp):
    releases = ["rhel-10.0", "rhel-9.9"]
    mock_pp.active_releases.return_value = releases
    jira_issue_prereq = factory.new_jira_issue_prerequisite(
        DUMMY_ISSUE, jira_issue="test"
    )
    rules = [factory.new_rule(prerequisites=[jira_issue_prereq]) for _ in range(2)]
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": release,
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test",
                                "create": f'{{"summary": "test", "labels": ["retasc-id-test-{release}"]}}',
                                "issue_id": ANY,
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                    for rule in rules
                ],
            }
            for release in releases
        ]
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
    input_issues = JiraIssues(jql=jql, fields=["description"])
    condition = "[jira_issue.key, jira_issue.fields.description]"
    condition_prereq = PrerequisiteCondition(condition=condition)
    rules = [
        factory.new_rule(inputs=[input_issues], prerequisites=[condition_prereq])
        for _ in range(2)
    ]
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "JiraIssues",
                "jira_issue": issue_id,
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "Condition",
                                "condition": condition,
                                "result": [issue_id, f"This is {issue_id}"],
                            }
                        ],
                        "state": "Completed",
                    }
                    for rule in rules
                ],
            }
            for issue_id in issue_ids
        ]
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
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_3",
                                "create": '{"summary": "test", "labels": ["retasc-id-test_jira_template_3-rhel-10.0"]}',
                                "issue_id": "TEST-1",
                                "state": "InProgress",
                                "subtasks": [
                                    {
                                        "type": "Subtask",
                                        "jira_issue": "test_jira_template_1",
                                        "create": '{"summary": "test", "labels": ["retasc-id-test_jira_template_1-rhel-10.0"]}',
                                        "issue_id": "TEST-2",
                                    },
                                    {
                                        "type": "Subtask",
                                        "jira_issue": "test_jira_template_2",
                                        "create": '{"summary": "test", "labels": ["retasc-id-test_jira_template_2-rhel-10.0"]}',
                                        "issue_id": "TEST-3",
                                    },
                                ],
                            },
                            {
                                "type": "Condition",
                                "condition": condition,
                                "result": [
                                    "test_jira_template_1",
                                    "test_jira_template_2",
                                    "test_jira_template_3",
                                ],
                            },
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
    }


def test_run_rule_jira_issue_in_progress(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "labels": issue_labels(jira_issue_prereq.jira_issue),
                "resolution": None,
                "summary": "test",
            },
        }
    ]
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_not_called()


def test_run_rule_jira_issue_not_unique(factory, mock_jira):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(DUMMY_ISSUE)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    mock_jira.search_issues.return_value = [
        {
            "key": f"TEST-{i}",
            "fields": {
                "labels": issue_labels(jira_issue_prereq.jira_issue),
                "resolution": None,
                "summary": "test",
            },
        }
        for i in [1, 2]
    ]

    expected_error = (
        "❌ Found multiple issues with the same ID label"
        " 'retasc-id-test_jira_template_1-rhel-10.0': 'TEST-1', 'TEST-2'"
    )
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "state": "Pending",
                                "error": expected_error,
                            }
                        ],
                        "state": "Pending",
                    }
                ],
            }
        ]
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
                "labels": issue_labels(jira_issue_prereq.jira_issue),
                "resolution": None,
                "summary": "test old",
            },
        }
    ]
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                                "update": '{"summary": "test"}',
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", {"summary": "test"})


def test_run_rule_jira_issue_update_labels(factory, mock_jira):
    """
    Make sure all requested labels are added to the existing Jira issue, but
    avoid removing any additional labels.
    """
    jira_issue_prereq = factory.new_jira_issue_prerequisite("""
        labels: [test1, test3]
    """)
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    old_labels = issue_labels(jira_issue_prereq.jira_issue) + ["test1", "test2"]
    expected_labels = issue_labels(jira_issue_prereq.jira_issue) + [
        "test1",
        "test2",
        "test3",
    ]
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
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                                "update": json.dumps({"labels": expected_labels}),
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
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
                "labels": ["retasc-id-test_jira_template_1-rhel-10.0"],
                "resolution": None,
            },
        }
    ]
    expected_fields = {"assignee": {"key": "alice"}}
    report = call_run(additional_jira_fields={"assignee": "assignee"})
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                                "update": json.dumps(expected_fields),
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", expected_fields)

    current_value["key"] = "alice"
    current_value["name"] = "Alice"
    report = call_run(additional_jira_fields={"assignee": "assignee"})
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
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
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "customfield_123": {
                    "value": "gating",
                    "child": {"id": "123", "value": "greenwave"},
                },
                "labels": ["retasc-id-test_jira_template_1-rhel-10.0"],
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
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                                "update": json.dumps(expected_fields),
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
    }
    mock_jira.create_issue.assert_not_called()
    mock_jira.edit_issue.assert_called_once_with("TEST-1", expected_fields)

    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {
                "customfield_123": {
                    "value": "gating",
                    "child": {"id": "123", "value": "waiverdb"},
                },
                "labels": ["retasc-id-test_jira_template_1-rhel-10.0"],
                "resolution": None,
            },
        }
    ]
    report = call_run(additional_jira_fields=additional_jira_fields)
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    }
                ],
            }
        ]
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
                "labels": issue_labels(jira_issue_prereq.jira_issue),
                "resolution": "Closed",
            },
        }
    ]
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                            }
                        ],
                        "state": "Completed",
                    }
                ],
            }
        ]
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
        issue_prereq = [
            {
                "type": "JiraIssue",
                "jira_issue": "test_jira_template_1",
                "create": '{"summary": "test", "labels": ["retasc-id-test_jira_template_1-rhel-10.0"]}',
                "issue_id": "TEST-1",
                "state": "InProgress",
            }
        ]
    else:
        issue_prereq = []

    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "Condition",
                                "condition": condition_expr,
                                "result": result,
                                **({} if result else {"state": "Pending"}),
                            },
                        ]
                        + issue_prereq,
                        "state": "InProgress" if result else "Pending",
                    }
                ],
            }
        ]
    }


def test_run_rule_template_error(factory):
    bad_condition = PrerequisiteCondition(condition="bad_template_variable")
    good_condition = PrerequisiteCondition(condition="true")
    rule1 = factory.new_rule(prerequisites=[bad_condition, good_condition])
    rule2 = factory.new_rule(prerequisites=[good_condition])

    report = call_run()
    expected_error = "'bad_template_variable' is undefined"
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule1.name,
                        "prerequisites": [
                            {
                                "type": "Condition",
                                "condition": "bad_template_variable",
                                "error": f"❌ {expected_error}",
                                "state": "Pending",
                            }
                        ],
                        "state": "Pending",
                    },
                    {
                        "rule": rule2.name,
                        "prerequisites": [
                            {
                                "type": "Condition",
                                "condition": "true",
                                "result": True,
                            }
                        ],
                        "state": "Completed",
                    },
                ],
            }
        ]
    }
    assert report.errors == [
        dedent(f"""
            {INPUT}
              Rule({rule1.name!r})
                Condition('bad_template_variable')
                  {expected_error}
        """).strip()
    ]


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
    mock_pp.release_schedules.return_value = [
        ProductPagesScheduleTask(
            name="TASK",
            start_date=date(1990, 1, 1),
            end_date=datetime.now(UTC).date(),
            is_draft=is_draft,
        ),
    ]
    factory.new_rule(
        prerequisites=[
            PrerequisiteSchedule(schedule_task="TASK"),
            PrerequisiteTargetDate(target_date=target_date),
        ]
    )

    state = "Completed" if result else "Pending"
    report = call_run()
    assert report.data["inputs"][0]["rules"][0]["state"] == state


def test_run_rule_schedule_missing(mock_pp, factory):
    mock_pp.release_schedules.return_value = []
    rule = factory.new_rule(prerequisites=[PrerequisiteSchedule(schedule_task="TASK")])

    report = call_run()
    assert report.data["inputs"][0]["rules"][0] == {
        "rule": rule.name,
        "prerequisites": [
            {
                "type": "Schedule",
                "schedule_task": "TASK",
                "state": "Pending",
                "pending_reason": "No schedule available yet",
            }
        ],
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
    mock_pp.release_schedules.return_value = [
        ProductPagesScheduleTask(
            name="TASK",
            start_date=date(1990, 1, 1),
            end_date=date(1990, 1, 3),
        ),
    ]
    schedule = PrerequisiteSchedule(schedule_task="TASK")
    condition = PrerequisiteCondition(condition=condition_expr)
    factory.new_rule(prerequisites=[schedule, condition])

    state = "Completed" if result else "Pending"
    report = call_run()
    assert report.data["inputs"][0]["rules"][0]["state"] == state


def test_run_rule_jira_issue_reserved_labels(factory):
    jira_issue_prereq = factory.new_jira_issue_prerequisite(
        "labels: [retasc-id-test1, retasc-id-test2]"
    )
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    expected_error = (
        "❌ Jira issue labels must not use reserved prefix"
        " 'retasc-id-': 'retasc-id-test1', 'retasc-id-test2'"
    )
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "error": expected_error,
                                "state": "Pending",
                            }
                        ],
                        "state": "Pending",
                    }
                ],
            }
        ]
    }


def test_run_rule_jira_issue_labels_must_be_list(factory):
    jira_issue_prereq = factory.new_jira_issue_prerequisite("labels: test1")
    rule = factory.new_rule(prerequisites=[jira_issue_prereq])
    expected_error = '❌ Jira issue field "labels" must be a list'
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "error": expected_error,
                                "state": "Pending",
                            }
                        ],
                        "state": "Pending",
                    }
                ],
            }
        ]
    }


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
        "inputs": [
            {
                "type": "JiraIssues",
                "jira_issue": f"TEST-{i}",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "Condition",
                                "condition": condition,
                                "result": issue,
                            }
                        ],
                        "state": "Completed",
                    }
                ],
            }
            for i, issue in enumerate(mock_jira.search_issues.return_value, start=1)
        ]
    }


def test_run_rule_jira_issue_input_field_names(factory, mock_jira):
    """Use only nice Jira issue names from 'jira_fields' config mapping."""
    mock_jira.search_issues.return_value = [
        {
            "key": "TEST-1",
            "fields": {"customfield_123": "test_value"},
        },
    ]
    condition_prereq = PrerequisiteCondition(condition="jira_issue")
    rule = factory.new_rule(
        inputs=[JiraIssues(jql="labels=test-label", fields=[])],
        prerequisites=[condition_prereq],
    )
    additional_jira_fields = {"human_readable_name": "customfield_123"}
    report = call_run(additional_jira_fields=additional_jira_fields)
    expected_issue = {
        "key": "TEST-1",
        "fields": {"human_readable_name": "test_value"},
    }
    assert report.data == {
        "inputs": [
            {
                "type": "JiraIssues",
                "jira_issue": "TEST-1",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "Condition",
                                "condition": "jira_issue",
                                "result": expected_issue,
                            }
                        ],
                        "state": "Completed",
                    }
                ],
            }
        ]
    }


def test_run_rule_jira_issue_dependency(factory: Factory, mock_jira):
    """
    Jira issue attributes from dependent rules are accessible in templates.
    """
    rule1 = factory.new_rule(
        prerequisites=[factory.new_jira_issue_prerequisite(DUMMY_ISSUE)],
    )
    jira_issue_prereq = factory.new_jira_issue_prerequisite(
        """
        summary: depends on {{ jira_issues.test_jira_template_1["key"] }}
        description: |-
            dependency is {{
                "Completed" if jira_issues.test_jira_template_1.fields.resolution | default() else
                "In Progress"
            }}
        """
    )
    rule2 = factory.new_rule(
        prerequisites=[
            PrerequisiteRule(rule=rule1.name),
            jira_issue_prereq,
        ],
    )
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule1.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "create": '{"summary": "test", "labels": ["retasc-id-test_jira_template_1-rhel-10.0"]}',
                                "issue_id": "TEST-1",
                                "state": "InProgress",
                            }
                        ],
                        "state": "InProgress",
                    },
                    {
                        "rule": rule2.name,
                        "prerequisites": [
                            {
                                "type": "Rule",
                                "rule": rule1.name,
                                "state": "InProgress",
                            },
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_2",
                                "create": '{"summary": "depends on TEST-1", "description": "dependency is In Progress", "labels": ["retasc-id-test_jira_template_2-rhel-10.0"]}',
                                "issue_id": "TEST-2",
                                "state": "InProgress",
                            },
                        ],
                        "state": "InProgress",
                    },
                ],
            }
        ]
    }

    # mock existing issues in Jira for the second run
    def search_issues(jql, fields):
        if "test_jira_template_1" in jql:
            return [
                {
                    "key": "TEST-1",
                    "fields": {
                        "summary": "test",
                        "labels": ["retasc-id-test_jira_template_1-rhel-10.0"],
                        "resolution": "Done",
                    },
                }
            ]
        return [
            {
                "key": "TEST-2",
                "fields": {
                    "summary": "depends on TEST-1",
                    "description": "dependency is In Progress",
                    "labels": ["retasc-id-test_jira_template_2-rhel-10.0"],
                    "resolution": None,
                },
            }
        ]

    mock_jira.search_issues.side_effect = search_issues
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule1.name,
                        "prerequisites": [
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_1",
                                "issue_id": "TEST-1",
                            }
                        ],
                        "state": "Completed",
                    },
                    {
                        "rule": rule2.name,
                        "prerequisites": [
                            {
                                "type": "Rule",
                                "rule": rule1.name,
                            },
                            {
                                "type": "JiraIssue",
                                "jira_issue": "test_jira_template_2",
                                "issue_id": "TEST-2",
                                "update": '{"description": "dependency is Completed"}',
                                "state": "InProgress",
                            },
                        ],
                        "state": "InProgress",
                    },
                ],
            }
        ]
    }


def test_run_rule_prerequsite_variable(factory):
    rule_data = {
        "version": 1,
        "name": "test-rule",
        "prerequisites": [
            {"variable": "test_var", "value": "release"},
            {"condition": "test_var"},
        ],
    }
    rule = Rule(**rule_data)
    factory.add_rule(rule)
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "Variable",
                                "variable": "test_var",
                                "value": "rhel-10.0",
                            },
                            {
                                "type": "Condition",
                                "condition": "test_var",
                                "result": "rhel-10.0",
                            },
                        ],
                        "state": "Completed",
                    }
                ],
            }
        ]
    }


def test_run_rule_prerequsite_variable_string(factory):
    rule_data = {
        "version": 1,
        "name": "test-rule",
        "prerequisites": [
            {"variable": "test_var", "string": "{{ release }}"},
            {"condition": "test_var"},
        ],
    }
    rule = Rule(**rule_data)
    factory.add_rule(rule)
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": rule.name,
                        "prerequisites": [
                            {
                                "type": "VariableString",
                                "variable": "test_var",
                                "value": "rhel-10.0",
                            },
                            {
                                "type": "Condition",
                                "condition": "test_var",
                                "result": "rhel-10.0",
                            },
                        ],
                        "state": "Completed",
                    }
                ],
            }
        ]
    }


def test_run_rule_inherit_params(factory):
    """Template parameters are inherited from dependent rules"""
    rule_data_list = [
        {
            "version": 1,
            "name": "rule-1",
            "prerequisites": [
                {"variable": "test_var", "string": "rule-1"},
                {"condition": "test_var"},
            ],
        },
        {
            "version": 1,
            "name": "rule-2",
            "prerequisites": [
                {"rule": "rule-1"},
                {"condition": "test_var"},
            ],
        },
        {
            "version": 1,
            "name": "rule-3",
            "prerequisites": [
                {"variable": "test_var", "string": "rule-2"},
                {"rule": "rule-1"},
                {"condition": "test_var"},
            ],
        },
        {
            "version": 1,
            "name": "rule-4",
            "prerequisites": [
                {"condition": "test_var|default"},
            ],
        },
    ]
    for rule_data in rule_data_list:
        factory.add_rule(Rule(**rule_data))
    report = call_run()
    assert report.data == {
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": "rule-1",
                        "prerequisites": [
                            {
                                "type": "VariableString",
                                "variable": "test_var",
                                "value": "rule-1",
                            },
                            {
                                "type": "Condition",
                                "condition": "test_var",
                                "result": "rule-1",
                            },
                        ],
                        "state": "Completed",
                    },
                    {
                        "rule": "rule-2",
                        "prerequisites": [
                            {
                                "type": "Rule",
                                "rule": "rule-1",
                            },
                            {
                                "type": "Condition",
                                "condition": "test_var",
                                "result": "rule-1",
                            },
                        ],
                        "state": "Completed",
                    },
                    {
                        "rule": "rule-3",
                        "prerequisites": [
                            {
                                "type": "VariableString",
                                "variable": "test_var",
                                "value": "rule-2",
                            },
                            {
                                "type": "Rule",
                                "rule": "rule-1",
                            },
                            {
                                "type": "Condition",
                                "condition": "test_var",
                                "result": "rule-1",
                            },
                        ],
                        "state": "Completed",
                    },
                    {
                        "rule": "rule-4",
                        "prerequisites": [
                            {
                                "type": "Condition",
                                "condition": "test_var|default",
                                "result": "",
                                "state": "Pending",
                            },
                        ],
                        "state": "Pending",
                    },
                ],
            }
        ],
    }
