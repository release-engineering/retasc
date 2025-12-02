# SPDX-License-Identifier: GPL-3.0-or-later

from textwrap import dedent
from typing import Any

from pydantic import BaseModel, Field


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


class HttpBase(BaseModel):
    """Base class for HTTP-based inputs and prerequisites."""

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
