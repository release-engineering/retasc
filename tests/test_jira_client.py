from unittest.mock import patch

import pytest

from retasc.jira_client import JiraClient


@pytest.fixture
def mock_jira():
    with patch("retasc.jira_client.Jira") as mock:
        yield mock


@pytest.fixture
def jira_client(mock_jira):
    return JiraClient("https://jira.example.com", token="dummy-token")


def test_create_basic_issue(jira_client, mock_jira):
    project_key = "TEST"
    summary = "Test summary"
    description = "Test description"
    issue_type = "Story"

    expected_issue_dict = {
        "project": {"key": project_key},
        "summary": summary,
        "description": description,
        "issuetype": {"name": issue_type},
    }

    mock_jira.return_value.issue_create.return_value = {"key": "TEST-456"}

    result = jira_client.create_issue(project_key, summary, description, issue_type)

    mock_jira.return_value.issue_create.assert_called_once_with(expected_issue_dict)
    assert result == {"key": "TEST-456"}


def test_create_issue_with_additional_fields(jira_client, mock_jira):
    project_key = "TEST"
    summary = "Test summary"
    description = "Test description"
    issue_type = "Story"
    fields = {"priority": {"name": "High"}}

    expected_issue_dict = {
        "project": {"key": project_key},
        "summary": summary,
        "description": description,
        "issuetype": {"name": issue_type},
        "priority": {"name": "High"},
    }

    mock_jira.return_value.issue_create.return_value = {"key": "TEST-456"}

    result = jira_client.create_issue(
        project_key, summary, description, issue_type, fields
    )

    mock_jira.return_value.issue_create.assert_called_once_with(expected_issue_dict)
    assert result == {"key": "TEST-456"}


def test_update_issue(jira_client, mock_jira):
    issue_key = "TEST-123"
    fields = {"summary": "Updated summary"}

    jira_client.update_issue(issue_key, fields)

    mock_jira.return_value.issue_update.assert_called_once_with(issue_key, fields)


def test_delete_issue(jira_client, mock_jira):
    issue_key = "TEST-789"

    jira_client.delete_issue(issue_key)

    mock_jira.return_value.delete_issue.assert_called_once_with(issue_key)


def test_get_issue(jira_client, mock_jira):
    issue_key = "TEST-101"
    mock_issue = {"key": issue_key, "fields": {"summary": "Test issue"}}
    mock_jira.return_value.issue.return_value = mock_issue

    result = jira_client.get_issue(issue_key)

    mock_jira.return_value.issue.assert_called_once_with(issue_key)
    assert result == mock_issue


def test_getattr_calls_jira_method(jira_client, mock_jira):
    mock_jira.return_value.get_issues_for_board.return_value = []

    issues = jira_client.get_issues_for_board(board_id=123)

    mock_jira.return_value.get_issues_for_board.assert_called_once_with(board_id=123)
    assert issues == []
