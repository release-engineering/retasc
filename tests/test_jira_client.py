# SPDX-License-Identifier: GPL-3.0-or-later
from unittest.mock import patch

from pytest import fixture, raises
from requests import Response, Session

from retasc.jira_client import DryRunJiraClient, JiraClient

JIRA_URL = "https://issues.example.com"

ISSUE_FIELDS = {
    "project": {"key": "TEST"},
    "issuetype": {"name": "Task"},
    "summary": "test rest",
    "description": "rest rest",
}
ISSUE_KEY = "TEST-1"

TEST_RES = {"id": "1", "key": "TEST-1"}

JQL = "project = TEST"
SEARCH_LIST = {"issues": [{"id": "10000", "key": "TEST-1"}], "total": 1}


@fixture
def jira_api():
    return JiraClient(JIRA_URL, token="DUMMY-TOKEN", session=Session())


@fixture
def dryrun_jira_api():
    return DryRunJiraClient(JIRA_URL, token="DUMMY-TOKEN", session=Session())


def test_create_issue(jira_api, requests_mock):
    requests_mock.post(
        f"{JIRA_URL}/rest/api/2/issue?updateHistory=false", json=TEST_RES
    )
    resp = jira_api.create_issue(ISSUE_FIELDS)
    assert resp == TEST_RES


def test_create_issue_dryrun(dryrun_jira_api, requests_mock):
    resp = dryrun_jira_api.create_issue(ISSUE_FIELDS)
    assert resp == {"key": "DRYRUN", "fields": {"resolution": None, **ISSUE_FIELDS}}


def test_edit_issue(jira_api, requests_mock):
    requests_mock.put(
        f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}?notifyUsers=True", json=TEST_RES
    )
    resp = jira_api.edit_issue(ISSUE_KEY, ISSUE_FIELDS)
    assert not bool(resp)


def test_edit_issue_dryrun(dryrun_jira_api, requests_mock):
    dryrun_jira_api.edit_issue("TEST", ISSUE_FIELDS)


def test_get_issue(jira_api, requests_mock):
    requests_mock.get(f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}", json=TEST_RES)
    resp = jira_api.get_issue(ISSUE_KEY)
    assert resp["key"] == ISSUE_KEY


def test_search_issues(jira_api, requests_mock):
    requests_mock.get(f"{JIRA_URL}/rest/api/2/search", json=SEARCH_LIST)
    issues = jira_api.search_issues(JQL)
    assert issues == [{"id": "10000", "key": ISSUE_KEY}]
    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].qs["jql"] == [JQL.lower()]


def test_search_issues_fields(jira_api, requests_mock):
    requests_mock.get(f"{JIRA_URL}/rest/api/2/search", json=SEARCH_LIST)
    issues = jira_api.search_issues(JQL, fields=["a", "b"])
    assert issues == [{"id": "10000", "key": ISSUE_KEY}]
    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].qs["jql"] == [JQL.lower()]
    assert requests_mock.request_history[0].qs["fields"] == ["a,b"]


def test_unexpected_response_create_issue(jira_api, requests_mock):
    requests_mock.post(f"{JIRA_URL}/rest/api/2/issue", json=[])
    with raises(RuntimeError, match=r"Unexpected response: \[\]"):
        jira_api.create_issue(ISSUE_FIELDS)


def test_unexpected_response_get_issue(jira_api, requests_mock):
    requests_mock.get(f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}", json=[])
    with raises(RuntimeError, match=r"Unexpected response: \[\]"):
        jira_api.get_issue(ISSUE_KEY)


def test_timeout(requests_mock):
    """
    The default timeout in atlassian.Jira API is 75 seconds for both the
    connection and the request. This should be overridden in JiraClient so it
    is possible to set different timeouts for connection and request or use
    None.
    """
    requests_mock.get(f"{JIRA_URL}/rest/api/2/search", json=SEARCH_LIST)
    session = Session()
    jira_api = JiraClient(JIRA_URL, token="DUMMY-TOKEN", session=session)
    with patch.object(session, "request") as mock_request:
        response = Response()
        response.status_code = 200
        mock_request.return_value = response
        jira_api.search_issues(JQL)
        assert len(mock_request.mock_calls) == 1
        _name, _args, kwargs = mock_request.mock_calls[0]
        assert kwargs.get("timeout") is None, kwargs
