# SPDX-License-Identifier: GPL-3.0-or-later
from pytest import fixture

from retasc.jira_client import JiraClient
import json

import pdb
JIRA_URL = "https://issues.example.com"

ISSUE_FIELDS={
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

TEST_RES ={
    "id": "1",
    "key": "TEST-1"
}

@fixture
def jira_api():
    return JiraClient(JIRA_URL)

def test_get_jira_url_info(jira_api):
    assert jira_api.api_url_issue() == JIRA_URL + "/rest/api/2/issue/"

def test_get_api_url_create_issue(jira_api):
    assert jira_api.api_url_create_issue() == JIRA_URL + "/rest/api/2/issue?updateHistory=false"

def test_create_issue(jira_api, requests_mock):
    requests_mock.post(jira_api.api_url_create_issue(), json=TEST_RES)
    resp = jira_api.create_issue(PROJECT_KEY, SUMMARY, DESCRIPTION, ISSUE_TYPE)
    req = requests_mock.request_history[0]
    assert resp == TEST_RES

def test_edit_issue(jira_api, requests_mock):
    requests_mock.put(jira_api.api_url_edit_issue(ISSUE_KEY), json=TEST_RES)
    resp = jira_api.edit_issue(ISSUE_KEY, ISSUE_FIELDS)
    req = requests_mock.request_history[0]
    assert not bool(resp)

def test_get_issue(jira_api, requests_mock):
    requests_mock.get(jira_api.api_url_issue("TEST-1"), json=TEST_RES)
    resp = jira_api.get_issue("TEST-1")
    assert resp["key"] == "TEST-1"
