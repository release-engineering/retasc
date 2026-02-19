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


def test_current_user_key(jira_api, requests_mock):
    requests_mock.get(f"{JIRA_URL}/rest/api/2/myself", json={"key": "retasc-bot"})
    assert jira_api.current_user_key == "retasc-bot"


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
    resp = jira_api.get_issue(ISSUE_KEY, fields=["summary", "description"])
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
        jira_api.get_issue(ISSUE_KEY, fields=["summary", "description"])


def test_unexpected_response_current_user_key(jira_api, requests_mock):
    requests_mock.get(f"{JIRA_URL}/rest/api/2/myself", json=[])
    with raises(RuntimeError, match=r"Unexpected response: \[\]"):
        jira_api.current_user_key


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


def test_add_comment(jira_api, requests_mock):
    comment_text = "Test comment"
    expected_response = {"id": "12345", "body": comment_text}
    requests_mock.post(
        f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}/comment", json=expected_response
    )
    resp = jira_api.add_comment(ISSUE_KEY, comment_text)
    assert resp == expected_response


def test_add_comment_dryrun(dryrun_jira_api, requests_mock):
    comment_text = "Test comment"
    resp = dryrun_jira_api.add_comment(ISSUE_KEY, comment_text)
    assert resp == {"id": "1", "body": comment_text}
    assert len(requests_mock.request_history) == 0


def test_get_issue_comments(jira_api, requests_mock):
    expected_response = {
        "comments": [
            {"id": "1", "body": "First comment"},
            {"id": "2", "body": "Second comment"},
        ]
    }
    requests_mock.get(
        f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}/comment", json=expected_response
    )
    resp = jira_api.get_issue_comments(ISSUE_KEY)
    assert resp == expected_response


def test_get_issue_comments_dryrun(dryrun_jira_api, requests_mock):
    resp = dryrun_jira_api.get_issue_comments(ISSUE_KEY)
    assert resp == {"comments": []}
    assert len(requests_mock.request_history) == 0


def test_unexpected_response_add_comment(jira_api, requests_mock):
    requests_mock.post(f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}/comment", json=[])
    with raises(RuntimeError, match=r"Unexpected response: \[\]"):
        jira_api.add_comment(ISSUE_KEY, "Test comment")


def test_unexpected_response_get_issue_comments(jira_api, requests_mock):
    requests_mock.get(f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}/comment", json=[])
    with raises(RuntimeError, match=r"Unexpected response: \[\]"):
        jira_api.get_issue_comments(ISSUE_KEY)


TRANSITIONS_URL = f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}/transitions"

TRANSITIONS_RESPONSE = {
    "transitions": [
        {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
        {"id": "21", "name": "Close", "to": {"name": "Closed"}},
    ]
}


def test_get_issue_transitions(jira_api, requests_mock):
    requests_mock.get(TRANSITIONS_URL, json=TRANSITIONS_RESPONSE)
    result = jira_api.get_issue_transitions(ISSUE_KEY)
    assert result == [
        {"name": "Start Progress", "id": 11, "to": "In Progress"},
        {"name": "Close", "id": 21, "to": "Closed"},
    ]


def test_get_issue_transitions_dryrun(dryrun_jira_api, requests_mock):
    result = dryrun_jira_api.get_issue_transitions(ISSUE_KEY)
    assert result == []
    assert len(requests_mock.request_history) == 0


def test_set_issue_status_direct(jira_api, requests_mock):
    """Direct transition when desired status is immediately reachable."""
    requests_mock.get(TRANSITIONS_URL, json=TRANSITIONS_RESPONSE)
    requests_mock.post(TRANSITIONS_URL, status_code=204)
    jira_api.set_issue_status(ISSUE_KEY, "Closed")
    posts = [r for r in requests_mock.request_history if r.method == "POST"]
    assert len(posts) == 1
    assert posts[0].json() == {"transition": {"id": 21}}


def test_set_issue_status_multi_step(jira_api, requests_mock):
    """Two-step traversal to reach the desired status."""
    step1_transitions = {
        "transitions": [
            {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
        ]
    }
    step2_transitions = {
        "transitions": [
            {"id": "31", "name": "Resolve", "to": {"name": "Resolved"}},
        ]
    }
    requests_mock.get(
        TRANSITIONS_URL, [{"json": step1_transitions}, {"json": step2_transitions}]
    )
    requests_mock.post(TRANSITIONS_URL, status_code=204)
    jira_api.set_issue_status(ISSUE_KEY, "Resolved")
    posts = [r for r in requests_mock.request_history if r.method == "POST"]
    assert len(posts) == 2
    assert posts[0].json() == {"transition": {"id": 11}}
    assert posts[1].json() == {"transition": {"id": 31}}


def test_set_issue_status_unreachable(jira_api, requests_mock):
    """Raises RuntimeError when the desired status cannot be reached."""
    requests_mock.get(TRANSITIONS_URL, json={"transitions": []})
    with raises(RuntimeError, match=r"Cannot reach status 'Done' for issue TEST-1"):
        jira_api.set_issue_status(ISSUE_KEY, "Done")


def test_set_issue_status_case_insensitive(jira_api, requests_mock):
    """Lowercase input matches capitalized status name."""
    requests_mock.get(TRANSITIONS_URL, json=TRANSITIONS_RESPONSE)
    requests_mock.post(TRANSITIONS_URL, status_code=204)
    jira_api.set_issue_status(ISSUE_KEY, "closed")
    posts = [r for r in requests_mock.request_history if r.method == "POST"]
    assert len(posts) == 1
    assert posts[0].json() == {"transition": {"id": 21}}


def test_set_issue_status_max_transitions_exhausted(jira_api, requests_mock):
    """Raises RuntimeError when max_transitions is exhausted."""
    # Each step offers a new unique intermediate status, never the target
    steps = [
        {
            "json": {
                "transitions": [
                    {"id": str(i), "name": f"Go {i}", "to": {"name": f"Status{i}"}}
                ]
            }
        }
        for i in range(3)
    ]
    requests_mock.get(TRANSITIONS_URL, steps)
    requests_mock.post(TRANSITIONS_URL, status_code=204)
    with raises(RuntimeError, match=r"Cannot reach status 'Done' for issue TEST-1"):
        jira_api.set_issue_status(ISSUE_KEY, "Done", max_transitions=3)


def test_set_issue_status_all_visited(jira_api, requests_mock):
    """Raises RuntimeError when all transitions lead to visited statuses."""
    step1 = {
        "transitions": [
            {"id": "11", "name": "Go to A", "to": {"name": "A"}},
        ]
    }
    # After transitioning to A, only transition goes back to a visited status
    step2 = {
        "transitions": [
            {"id": "12", "name": "Go back", "to": {"name": "A"}},
        ]
    }
    requests_mock.get(TRANSITIONS_URL, [{"json": step1}, {"json": step2}])
    requests_mock.post(TRANSITIONS_URL, status_code=204)
    with raises(RuntimeError, match=r"Cannot reach status 'Done' for issue TEST-1"):
        jira_api.set_issue_status(ISSUE_KEY, "Done")


def test_set_issue_status_dryrun(dryrun_jira_api, requests_mock):
    dryrun_jira_api.set_issue_status(ISSUE_KEY, "Closed")
    assert len(requests_mock.request_history) == 0


def test_unexpected_response_get_issue_transitions(jira_api):
    with patch.object(jira_api.jira, "get_issue_transitions", return_value="bad"):
        with raises(RuntimeError, match=r"Unexpected response"):
            jira_api.get_issue_transitions(ISSUE_KEY)
