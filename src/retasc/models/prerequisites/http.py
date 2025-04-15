# SPDX-License-Identifier: GPL-3.0-or-later

from textwrap import dedent
from typing import Any

from pydantic import Field
from requests.exceptions import RequestException

from retasc.models.prerequisites.base import PrerequisiteBase
from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.release_rule_state import ReleaseRuleState


def render_templates(value, context):
    if isinstance(value, str):
        return context.template.render(value)

    if isinstance(value, list):
        return [render_templates(x, context) for x in value]

    if isinstance(value, dict):
        return {k: render_templates(v, context) for k, v in value.items()}

    return value


class PrerequisiteHttp(PrerequisiteBase):
    """
    Make an HTTP request.

    Raises an error if the request fails due to connection error, timeout, SSL
    issues, etc.

    Adds http_response template parameter (the type is requests.Response).
    """

    url: str = Field(description="URL template for the request")
    method: str = Field(
        description="HTTP method to use (default is GET)", default="GET"
    )
    params: dict[str, Any] = Field(
        description="URL parameters; values can be templates", default_factory=dict
    )
    json: Any | None = Field(
        description=dedent("""
            If set, a data (list, dict etc) to encode as JSON and pass in the
            request body.
        """).strip(),
        default=None,
    )

    def update_state(self, context) -> ReleaseRuleState:
        url = context.template.render(self.url)
        params = render_templates(self.params, context)
        json = render_templates(self.json, context)

        try:
            context.template.params["http_response"] = context.session.request(
                self.method, url, params=params, json=json
            )
        except RequestException as e:
            raise PrerequisiteUpdateStateError(f"HTTP request failed: {e}")

        return ReleaseRuleState.Completed
