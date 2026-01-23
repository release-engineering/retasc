# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

from pytest import fixture

from retasc.models.prerequisites.jira_issue import PrerequisiteJiraIssue
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.report import Report
from retasc.templates.template_manager import TemplateManager


@fixture
def mock_context():
    context = Mock()
    context.jira = Mock()
    context.template = TemplateManager(template_search_path=Path())
    context.report = Report()
    context.config = Mock()
    context.config.jira_label_prefix = "retasc-id-"
    context.config.from_jira_field_name = lambda x: x
    context.config.to_jira_field_name = lambda x: x
    context.config.jira_template_path = Path()
    context.template.params = {"jira_label_suffix": "-test"}
    yield context


def test_comment_added_to_new_issue(mock_context):
    """Test that a comment is added when creating a new issue."""
    comment_text = "Test comment"

    mock_context.jira.search_issues.return_value = []
    mock_context.jira.create_issue.return_value = {
        "key": "TEST-1",
        "fields": {"resolution": None, "summary": "test"},
    }
    mock_context.jira.get_issue_comments.return_value = {"comments": []}
    mock_context.jira.add_comment.return_value = {"id": "1", "body": comment_text}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        comment=comment_text,
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.add_comment.assert_called_once_with("TEST-1", comment_text)
    assert mock_context.report.current_data.get("comment_status") == "added"


def test_comment_templated(mock_context):
    """Test that template variables are rendered in comments."""
    mock_context.template.params["pipeline_run"] = {
        "state": "Succeeded",
        "url": "https://example.com/run/123",
    }

    comment_template = dedent("""
        Pipeline run status: {{ pipeline_run.state }}
        Pipeline run: {{ pipeline_run.url }}
    """).strip()

    expected_comment = dedent("""
        Pipeline run status: Succeeded
        Pipeline run: https://example.com/run/123
    """).strip()

    mock_context.jira.search_issues.return_value = []
    mock_context.jira.create_issue.return_value = {
        "key": "TEST-2",
        "fields": {"resolution": None, "summary": "test"},
    }
    mock_context.jira.get_issue_comments.return_value = {"comments": []}
    mock_context.jira.add_comment.return_value = {"id": "2", "body": expected_comment}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue-2",
        template=None,
        fields={"summary": "test"},
        comment=comment_template,
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.add_comment.assert_called_once_with("TEST-2", expected_comment)


def test_comment_skipped_duplicate(mock_context):
    """Test that duplicate comments are not added."""
    comment_text = "Test comment"

    mock_context.jira.search_issues.return_value = [
        {
            "key": "TEST-3",
            "fields": {"resolution": None, "summary": "test", "labels": []},
        }
    ]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}
    mock_context.jira.get_issue_comments.return_value = {
        "comments": [{"id": "1", "body": comment_text}]
    }

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue-3",
        template=None,
        fields={"summary": "test"},
        comment=comment_text,
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.add_comment.assert_not_called()
    assert mock_context.report.current_data.get("comment_status") == "skipped_duplicate"


def test_comment_not_added_to_resolved_issue(mock_context):
    """Test that comments are not added to resolved issues."""
    comment_text = "Test comment"

    mock_context.jira.search_issues.return_value = [
        {
            "key": "TEST-5",
            "fields": {
                "resolution": {"name": "Done"},
                "summary": "test",
                "labels": [],
            },
        }
    ]

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue-5",
        template=None,
        fields={"summary": "test"},
        comment=comment_text,
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.Completed
    mock_context.jira.add_comment.assert_not_called()
    mock_context.jira.get_issue_comments.assert_not_called()
