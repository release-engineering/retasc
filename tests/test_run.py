# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date
from unittest.mock import Mock, call, patch

from pytest import fixture, mark

from retasc.models.prerequisites.condition import PrerequisiteCondition
from retasc.models.prerequisites.schedule import PrerequisiteSchedule
from retasc.product_pages_api import ProductPagesScheduleTask
from retasc.run import run

from .common_run import *  # noqa: F403
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
def factory(tmpdir):
    return Factory(tmpdir)


def test_run_rule_simple(mock_parse_rules, factory):
    rule = factory.new_rule(name="rule1")
    mock_parse_rules.return_value = {"test_rule1": rule}
    print = Mock()

    run(dry_run=True, print=print)
    print.assert_has_calls(
        [
            call("Product 'rhel'"),
            call("- Release 'rhel-10.0'"),
            call("-- Rule 'rule1' state: Completed"),
        ]
    )


def test_run_rule_simple_in_progress(mock_parse_rules, factory):
    template = factory.new_jira_template(DUMMY_ISSUE)
    rule = factory.new_rule(jira_issues=[template])
    mock_parse_rules.return_value = {"test_rule1": rule}
    print = Mock()

    run(dry_run=True, print=print)
    print.assert_has_calls(
        [
            call("Product 'rhel'"),
            call("- Release 'rhel-10.0'"),
            call(f"-- Rule '{rule.name}' state: InProgress"),
        ]
    )


@mark.parametrize(
    ("condition_expr", "result"),
    (
        ("true", True),
        ("major >= 10", True),
        ("false", False),
        ("major < 10", False),
    ),
)
def test_run_rule_condition_disabled(condition_expr, result, mock_parse_rules, factory):
    template = factory.new_jira_template(DUMMY_ISSUE)
    condition = PrerequisiteCondition(condition=condition_expr)
    rule = factory.new_rule(prerequisites=[condition], jira_issues=[template])
    mock_parse_rules.return_value = {"test_rule1": rule}
    print = Mock()

    run(dry_run=True, print=print)
    state = "InProgress" if result else "Pending"
    print.assert_any_call(f"-- Rule '{rule.name}' state: {state}")


@mark.parametrize(
    ("day_delta", "condition_expr", "result"),
    (
        (0, "start_date.year == 2024", False),
        # start_date is minimum from all required schedule task
        (0, "start_date.year == 1990", True),
        (0, "start_date.month == 1", True),
        (0, "start_date.day == 1", True),
        # end_date is maximum from all required schedule task
        (0, "end_date | string == '1990-01-04'", True),
        # add 31 days
        (31, "start_date | string == '1990-02-01'", True),
        # end_date must be start_date or later
        (31, "end_date | string == '1990-02-02'", True),
    ),
)
def test_run_rule_schedule_params(
    day_delta, condition_expr, result, mock_pp, mock_parse_rules, factory
):
    mock_pp.release_schedules.return_value = {
        "TASK1": ProductPagesScheduleTask(
            start_date=date(1990, 1, 2),
            end_date=date(1990, 1, 2),
        ),
        "TASK2": ProductPagesScheduleTask(
            start_date=date(1990, 1, 3),
            end_date=date(1990, 1, 4),
        ),
        "TASK3": ProductPagesScheduleTask(
            start_date=date(1990, 1, 1),
            end_date=date(1990, 1, 3),
        ),
    }
    template = factory.new_jira_template(DUMMY_ISSUE)
    schedule1 = PrerequisiteSchedule(
        schedule_task="TASK1", days_before_or_after=day_delta
    )
    schedule2 = PrerequisiteSchedule(
        schedule_task="TASK2", days_before_or_after=day_delta
    )
    schedule3 = PrerequisiteSchedule(
        schedule_task="TASK3", days_before_or_after=day_delta
    )
    condition = PrerequisiteCondition(condition=condition_expr)
    rule = factory.new_rule(
        prerequisites=[schedule1, schedule2, schedule3, condition],
        jira_issues=[template],
    )
    mock_parse_rules.return_value = {"test_rule1": rule}
    print = Mock()

    state = "InProgress" if result else "Pending"
    run(dry_run=True, print=print)
    print.assert_any_call(f"-- Rule '{rule.name}' state: {state}")


def test_create_issue():
    pass


def test_drop_issue_when_rule_is_removed():
    pass


def test_update_issue_when_pp_date_changes():
    pass
