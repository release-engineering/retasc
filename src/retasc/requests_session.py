# SPDX-License-Identifier: GPL-3.0-or-later
"""
HTTP request client with retry capability
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HTTPAdapterWithTimeout(HTTPAdapter):
    """HTTPAdapter with default timeout for all requests"""

    def __init__(self, *, timeout: tuple[float, float], **kwargs):
        super().__init__(**kwargs)
        self.timeout = timeout

    def send(self, request, **kwargs):
        timeout = kwargs.pop("timeout", None)
        if timeout is None:
            timeout = self.timeout
        return super().send(request, timeout=timeout, **kwargs)


def requests_session(
    *, connect_timeout: float, read_timeout: float, retry_on_statuses: tuple = ()
):
    """Returns https session for request processing."""

    session = requests.Session()
    retry = Retry(
        total=5,
        read=3,
        connect=3,
        backoff_factor=1,
        status_forcelist=(*retry_on_statuses, 500, 502, 503, 504),
        allowed_methods=Retry.DEFAULT_ALLOWED_METHODS.union(("POST",)),
    )
    timeout = (connect_timeout, read_timeout)
    adapter = HTTPAdapterWithTimeout(max_retries=retry, timeout=timeout)
    session.mount("https://", adapter)
    session.headers["User-Agent"] = "sp-retasc-agent"
    session.headers["Content-type"] = "application/json"
    return session
