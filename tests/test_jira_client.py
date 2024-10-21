# SPDX-License-Identifier: GPL-3.0-or-later

from pytest import fixture

from retasc.jira_client import JiraClient

JIRA_URL = "https://issues.example.com"

ISSUE_FIELDS = {
    "project": {"key": "TEST"},
    "issuetype": {"name": "Task"},
    "summary": "test rest",
    "description": "rest rest",
}
PROJECT_KEY = "TEST"
ISSUE_KEY = "TEST-1"
SUMMARY = "summary test"
DESCRIPTION = "description test"
ISSUE_TYPE = "Story"

TEST_RES = {"id": "1", "key": "TEST-1"}

JQL = "project = TEST"
SEARCH_LIST = {"issues": [{"id": "10000", "key": "TEST-1"}]}


@fixture
def jira_api():
    return JiraClient(JIRA_URL)


def test_create_issue(jira_api, requests_mock):
    requests_mock.post(
        f"{JIRA_URL}/rest/api/2/issue?updateHistory=false", json=TEST_RES
    )
    resp = jira_api.create_issue(PROJECT_KEY, SUMMARY, DESCRIPTION, ISSUE_TYPE)
    requests_mock.request_history[0]
    assert resp == TEST_RES


def test_edit_issue(jira_api, requests_mock):
    requests_mock.put(
        f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}?notifyUsers=True", json=TEST_RES
    )
    resp = jira_api.edit_issue(ISSUE_KEY, ISSUE_FIELDS)
    requests_mock.request_history[0]
    assert not bool(resp)


def test_get_issue(jira_api, requests_mock):
    requests_mock.get(f"{JIRA_URL}/rest/api/2/issue/{ISSUE_KEY}", json=TEST_RES)
    resp = jira_api.get_issue("TEST-1")
    assert resp["key"] == "TEST-1"


def test_search_issue(jira_api, requests_mock):
    requests_mock.get(
        f"{JIRA_URL}/rest/api/2/search?startAt=0&fields=%2Aall&jql=project+%3D+{PROJECT_KEY}",
        json=SEARCH_LIST,
    )
    resp = jira_api.search_issue(JQL)
    assert resp["issues"][0]["id"] == "10000"
    assert resp["issues"][0]["key"] == "TEST-1"
