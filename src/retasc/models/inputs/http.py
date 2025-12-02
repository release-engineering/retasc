# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator
from textwrap import dedent

from pydantic import Field

from retasc.models.http_common import HttpBase, render_template_dict, render_templates
from retasc.models.inputs.base import InputBase
from retasc.models.inputs.exceptions import InputValuesError


class Http(HttpBase, InputBase):
    """
    Make an HTTP request and iterate over JSON response items.

    If the response is a JSON array, yields each item in the array.
    If inputs is specified, extracts the array from the response
    using that template expression.

    Adds the following template parameters for each item:
    - http_item - the current item from the JSON array
    - http_response - the full HTTP response (requests.Response)
    - http_data - the JSON response data (for use in inputs)
    """

    inputs: str = Field(
        description=dedent("""
            Template expression to extract the array from the JSON response.
            The JSON response is available as 'http_data'.
            Default is 'http_data' which expects the response itself to be an array.
            Examples: 'http_data.results', 'http_data["items"]', 'http_data.data.items'
        """).strip(),
        default="http_data",
    )

    def _make_request(self, context):
        """Make HTTP request and return the response."""
        url = context.template.render(self.url)
        headers = render_template_dict(self.headers, context)
        params = render_template_dict(self.params, context)
        data = render_templates(self.data, context)
        response = context.session.request(
            self.method, url, params=params, json=data, headers=headers
        )
        response.raise_for_status()
        return response

    def _extract_items(self, response, context):
        """Extract array items from JSON response."""
        try:
            http_data = response.json()
        except ValueError as e:
            raise InputValuesError(f"Failed to parse JSON response: {e}")

        context.template.params["http_data"] = http_data
        items = context.template.evaluate(self.inputs)

        if not isinstance(items, list):
            raise InputValuesError(
                f"Expression '{self.inputs}' did not return a list, got {items!r}"
            )

        return items

    def values(self, context) -> Iterator[dict]:
        response = self._make_request(context)
        items = self._extract_items(response, context)

        for index, item in enumerate(items):
            yield {
                "http_item": item,
                "http_response": response,
                "http_item_index": index,
            }

    def report_vars(self, values: dict) -> dict:
        return {
            "http_item": values.get("http_item"),
            "http_item_index": values.get("http_item_index"),
        }
