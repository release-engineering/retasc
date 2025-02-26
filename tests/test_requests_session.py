# SPDX-License-Identifier: GPL-3.0-or-later
from unittest.mock import patch

from pytest import fixture
from requests import Response

from retasc.requests_session import HTTPAdapter, requests_session


@fixture
def mock_http_adapter_send():
    with patch.object(
        HTTPAdapter, "send", autospec=True, return_value=Response()
    ) as send:
        yield send


def test_requests_session_timeout_default(mock_http_adapter_send):
    test_url = "https://example.com"
    session = requests_session(connect_timeout=1, read_timeout=2)
    session.get(test_url)
    assert len(mock_http_adapter_send.mock_calls) == 1
    _name, _args, kwargs = mock_http_adapter_send.mock_calls[0]
    assert kwargs.get("timeout") == (1, 2), kwargs


def test_requests_session_timeout(mock_http_adapter_send):
    test_url = "https://example.com"
    session = requests_session(connect_timeout=1, read_timeout=2)
    session.get(test_url, timeout=5)
    assert len(mock_http_adapter_send.mock_calls) == 1
    _name, _args, kwargs = mock_http_adapter_send.mock_calls[0]
    assert kwargs.get("timeout") == 5, kwargs
