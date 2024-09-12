# SPDX-License-Identifier: GPL-3.0-or-later
from unittest.mock import Mock, call, patch

from pytest import fixture

from retasc.run import run

from .common_run import mock_env, mock_jira, mock_pp  # noqa: F401
from .factory import Factory


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
            call("Release 'rhel-10.0'"),
            call("  Rule 'rule1' state: Completed"),
        ]
    )


def test_run_rule_simple_in_progress(mock_parse_rules, factory):
    template = factory.new_jira_template("""
        summary: test
    """)
    rule = factory.new_rule(jira_issues=[template])
    mock_parse_rules.return_value = {"test_rule1": rule}
    print = Mock()
    run(dry_run=True, print=print)
    print.assert_has_calls(
        [
            call("Release 'rhel-10.0'"),
            call(f"  Rule '{rule.name}' state: InProgress"),
        ]
    )


def test_create_issue():
    pass


def test_drop_issue_when_rule_is_removed():
    pass


def test_update_issue_when_pp_date_changes():
    pass
