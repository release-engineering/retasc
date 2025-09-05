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
        return render_template_dict(value, context)

    return value


def render_template_dict(value, context):
    return {k: render_templates(v, context) for k, v in value.items()}


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
    headers: dict[str, str] = Field(
        description="HTTP headers; values can be templates", default_factory=dict
    )
    params: dict[str, Any] = Field(
        description="URL parameters; values can be templates", default_factory=dict
    )
    data: Any | None = Field(
        description=dedent("""
            If set, a data (list, dict etc) to encode as JSON and pass in the
            request body.
        """).strip(),
        default=None,
    )

    def update_state(self, context) -> ReleaseRuleState:
        url = context.template.render(self.url)
        headers = render_template_dict(self.headers, context)
        params = render_template_dict(self.params, context)
        data = render_templates(self.data, context)

        try:
            context.template.params["http_response"] = context.session.request(
                self.method, url, params=params, json=data, headers=headers
            )
        except RequestException as e:
            raise PrerequisiteUpdateStateError(f"HTTP request failed: {e}")

        return ReleaseRuleState.Completed
