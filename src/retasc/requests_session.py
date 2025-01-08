# SPDX-License-Identifier: GPL-3.0-or-later
"""
HTTP request client with retry capability
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def requests_session(*, retry_on_statuses: tuple = ()):
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
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers["User-Agent"] = "sp-retasc-agent"
    session.headers["Content-type"] = "application/json"
    return session
