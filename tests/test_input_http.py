# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from unittest.mock import Mock

from jinja2.exceptions import TemplateError
from pytest import fixture, raises
from requests import Session
from requests.exceptions import ConnectTimeout, RequestException

from retasc.models.inputs.exceptions import InputValuesError
from retasc.models.inputs.http import Http
from retasc.templates.template_manager import TemplateManager

DEFAULT_USER_AGENT = "test-agent"


@fixture
def mock_context():
    context = Mock()
    context.session = Session()
    context.session.headers["User-Agent"] = DEFAULT_USER_AGENT
    context.template = TemplateManager(template_search_path=Path())
    yield context


def test_http_input_get_json_array(mock_context, requests_mock):
    url = "https://test.example.com/items"
    data = [
        {"id": 1, "name": "item1"},
        {"id": 2, "name": "item2"},
        {"id": 3, "name": "item3"},
    ]
    requests_mock.get(url, json=data)

    http_input = Http(url=url)
    values = list(http_input.values(mock_context))

    assert len(values) == 3
    for i, value in enumerate(values):
        assert value["http_item"] == data[i]
        assert value["http_item_index"] == i
        assert value["http_response"].status_code == 200

    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].headers["User-Agent"] == DEFAULT_USER_AGENT


def test_http_input_get_json_array_from_key(mock_context, requests_mock):
    url = "https://test.example.com/api/data"
    data = {
        "results": [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"},
        ],
        "total": 2,
    }
    requests_mock.get(url, json=data)

    http_input = Http(url=url, inputs="http_data.results")
    values = list(http_input.values(mock_context))

    assert len(values) == 2
    for i, value in enumerate(values):
        assert value["http_item"] == data["results"][i]
        assert value["http_item_index"] == i


def test_http_input_post_with_data(mock_context, requests_mock):
    url = "https://test.example.com/search"
    response_data = [{"id": 1, "match": "test"}]
    requests_mock.post(url, json=response_data)

    request_data = {"query": "test", "limit": 10}
    http_input = Http(url=url, method="POST", data=request_data)
    values = list(http_input.values(mock_context))

    assert len(values) == 1
    assert values[0]["http_item"] == response_data[0]

    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].json() == request_data


def test_http_input_with_headers(mock_context, requests_mock):
    url = "https://test.example.com/items"
    data = [{"id": 1}]
    requests_mock.get(url, json=data)

    headers = {"User-Agent": "custom-agent", "X-API-Key": "secret"}
    http_input = Http(url=url, headers=headers)
    list(http_input.values(mock_context))

    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].headers["User-Agent"] == "custom-agent"
    assert requests_mock.request_history[0].headers["X-API-Key"] == "secret"


def test_http_input_with_params(mock_context, requests_mock):
    url = "https://test.example.com/items"
    data = [{"id": 1}]
    requests_mock.get(url, json=data)

    params = {"page": 1, "limit": 10}
    http_input = Http(url=url, params=params)
    list(http_input.values(mock_context))

    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].qs == {"page": ["1"], "limit": ["10"]}


def test_http_input_template_rendering(mock_context, requests_mock):
    mock_context.template.params["api_url"] = "https://test.example.com"
    mock_context.template.params["endpoint"] = "items"

    url = "{{ api_url }}/{{ endpoint }}"
    data = [{"id": 1}]
    requests_mock.get("https://test.example.com/items", json=data)

    http_input = Http(url=url)
    values = list(http_input.values(mock_context))

    assert len(values) == 1
    assert values[0]["http_item"] == data[0]


def test_http_input_template_in_data(mock_context, requests_mock):
    mock_context.template.params["query_term"] = "test"

    url = "https://test.example.com/search"
    response_data = [{"id": 1}]
    requests_mock.post(url, json=response_data)

    request_data = {"query": "{{ query_term }}", "limit": 10}
    http_input = Http(url=url, method="POST", data=request_data)
    list(http_input.values(mock_context))

    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].json() == {"query": "test", "limit": 10}


def test_http_input_template_in_list_data(mock_context, requests_mock):
    mock_context.template.params["item1"] = "first"
    mock_context.template.params["item2"] = "second"

    url = "https://test.example.com/search"
    response_data = [{"id": 1}]
    requests_mock.post(url, json=response_data)

    request_data = ["{{ item1 }}", "{{ item2 }}"]
    http_input = Http(url=url, method="POST", data=request_data)
    list(http_input.values(mock_context))

    assert len(requests_mock.request_history) == 1
    assert requests_mock.request_history[0].json() == ["first", "second"]


def test_http_input_connection_error(mock_context, requests_mock):
    url = "https://test.example.com/items"
    requests_mock.get(url, exc=ConnectTimeout)

    http_input = Http(url=url)
    with raises(ConnectTimeout):
        list(http_input.values(mock_context))


def test_http_input_non_json_response(mock_context, requests_mock):
    url = "https://test.example.com/items"
    requests_mock.get(url, text="not json")

    http_input = Http(url=url)
    with raises(InputValuesError, match="Failed to parse JSON response"):
        list(http_input.values(mock_context))


def test_http_input_non_array_response(mock_context, requests_mock):
    url = "https://test.example.com/items"
    requests_mock.get(url, json={"message": "success"})

    http_input = Http(url=url)
    with raises(InputValuesError, match="did not return a list"):
        list(http_input.values(mock_context))


def test_http_input_missing_array_key(mock_context, requests_mock):
    url = "https://test.example.com/items"
    requests_mock.get(url, json={"total": 0})

    http_input = Http(url=url, inputs="http_data.results")
    with raises(InputValuesError, match="did not return a list, got Undefined"):
        list(http_input.values(mock_context))


def test_http_input_array_key_with_non_object(mock_context, requests_mock):
    url = "https://test.example.com/items"
    requests_mock.get(url, json=[1, 2, 3])

    http_input = Http(url=url, inputs="http_data.results")
    with raises(InputValuesError, match="did not return a list, got Undefined"):
        list(http_input.values(mock_context))


def test_http_input_array_key_contains_non_array(mock_context, requests_mock):
    url = "https://test.example.com/items"
    requests_mock.get(url, json={"results": "not an array"})

    http_input = Http(url=url, inputs="http_data.results")
    with raises(InputValuesError, match="did not return a list, got 'not an array"):
        list(http_input.values(mock_context))


def test_http_input_empty_array(mock_context, requests_mock):
    url = "https://test.example.com/items"
    requests_mock.get(url, json=[])

    http_input = Http(url=url)
    values = list(http_input.values(mock_context))

    assert len(values) == 0


def test_http_input_report_vars(mock_context, requests_mock):
    url = "https://test.example.com/items"
    data = [{"id": 1, "name": "item1"}]
    requests_mock.get(url, json=data)

    http_input = Http(url=url)
    values = list(http_input.values(mock_context))

    report_vars = http_input.report_vars(values[0])
    assert report_vars == {"url": url, "http_item_index": 0}


def test_http_input_http_error(mock_context, requests_mock):
    url = "https://test.example.com/items"
    requests_mock.get(url, status_code=404)

    http_input = Http(url=url)
    with raises(RequestException, match="404"):
        list(http_input.values(mock_context))


def test_http_input_inputs_bracket_notation(mock_context, requests_mock):
    url = "https://test.example.com/api/data"
    data = {
        "items": [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"},
        ],
    }
    requests_mock.get(url, json=data)

    http_input = Http(url=url, inputs="http_data['items']")
    values = list(http_input.values(mock_context))

    assert len(values) == 2
    for i, value in enumerate(values):
        assert value["http_item"] == data["items"][i]


def test_http_input_inputs_nested(mock_context, requests_mock):
    url = "https://test.example.com/api/data"
    data = {
        "response": {
            "data": {
                "results": [
                    {"id": 1, "name": "item1"},
                    {"id": 2, "name": "item2"},
                ],
            }
        }
    }
    requests_mock.get(url, json=data)

    http_input = Http(url=url, inputs="http_data.response.data.results")
    values = list(http_input.values(mock_context))

    assert len(values) == 2
    for i, value in enumerate(values):
        assert value["http_item"] == data["response"]["data"]["results"][i]


def test_http_input_inputs_with_template_vars(mock_context, requests_mock):
    url = "https://test.example.com/api/data"
    data = {
        "results": [{"id": 1}],
        "items": [{"id": 2}],
    }
    requests_mock.get(url, json=data)
    mock_context.template.params["array_key"] = "results"

    http_input = Http(url=url, inputs="http_data[array_key]")
    values = list(http_input.values(mock_context))

    assert len(values) == 1
    assert values[0]["http_item"] == data["results"][0]


def test_http_input_inputs_bracket_nested(mock_context, requests_mock):
    url = "https://test.example.com/api/data"
    data = {
        "response": {
            "items": [
                {"id": 1, "name": "item1"},
                {"id": 2, "name": "item2"},
            ],
        }
    }
    requests_mock.get(url, json=data)

    # Using bracket notation to avoid conflict with dict.items() method
    http_input = Http(url=url, inputs="http_data['response']['items']")
    values = list(http_input.values(mock_context))

    assert len(values) == 2
    for i, value in enumerate(values):
        assert value["http_item"] == data["response"]["items"][i]


def test_http_input_inputs_invalid_syntax(mock_context, requests_mock):
    url = "https://test.example.com/api/data"
    data = {"results": [{"id": 1}]}
    requests_mock.get(url, json=data)

    http_input = Http(url=url, inputs="http_data['results'")
    with raises(TemplateError):
        list(http_input.values(mock_context))
