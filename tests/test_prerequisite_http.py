# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from unittest.mock import Mock

from pytest import fixture, raises
from requests import Session
from requests.exceptions import ConnectTimeout, JSONDecodeError

from retasc.models.prerequisites.condition import PrerequisiteCondition
from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.prerequisites.http import PrerequisiteHttp
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.templates.template_manager import TemplateManager


@fixture
def mock_context():
    context = Mock()
    context.session = Session()
    context.template = TemplateManager(template_search_path=Path())
    yield context


def test_prerequisite_http_get(mock_context, requests_mock):
    url = "https://test.example.com"
    requests_mock.get(url)

    prereq = PrerequisiteHttp(url=url)
    assert prereq.update_state(mock_context) == ReleaseRuleState.Completed
    assert mock_context.template.params.get("http_response")
    assert mock_context.template.params["http_response"].status_code == 200


def test_prerequisite_http_response_template(mock_context, requests_mock):
    url = "https://test.example.com"
    data = {"items": [{"data": "test"}]}
    requests_mock.post(url, json=data)

    prereq = PrerequisiteHttp(url=url, method="post")
    assert prereq.update_state(mock_context) == ReleaseRuleState.Completed
    http_response = mock_context.template.params.get("http_response")
    assert http_response
    assert http_response.status_code == 200
    assert http_response.json() == data

    prereq_cond1 = PrerequisiteCondition(condition="http_response.status_code == 200")
    assert prereq_cond1.update_state(mock_context) == ReleaseRuleState.Completed

    prereq_cond2 = PrerequisiteCondition(
        condition="http_response.json()['items'][0].data == 'test'"
    )
    assert prereq_cond2.update_state(mock_context) == ReleaseRuleState.Completed


def test_prerequisite_http_json_template(mock_context, requests_mock):
    url = "https://test.example.com"
    requests_mock.post(url)

    data = {"items": [{"data": "{{ 'test' }}"}]}
    prereq = PrerequisiteHttp(url=url, method="POST", json=data)
    assert prereq.update_state(mock_context) == ReleaseRuleState.Completed
    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].json() == {"items": [{"data": "test"}]}


def test_prerequisite_http_bad_json(mock_context, requests_mock):
    url = "https://test.example.com"
    requests_mock.get(url)

    prereq = PrerequisiteHttp(url=url)
    assert prereq.update_state(mock_context) == ReleaseRuleState.Completed

    prereq_cond = PrerequisiteCondition(condition="http_response.json()")
    with raises(JSONDecodeError):
        prereq_cond.update_state(mock_context)


def test_prerequisite_http_fails(mock_context, requests_mock):
    url = "https://test.example.com"
    requests_mock.get(url, exc=ConnectTimeout)

    prereq = PrerequisiteHttp(url=url)
    with raises(PrerequisiteUpdateStateError):
        prereq.update_state(mock_context)
