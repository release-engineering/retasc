# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Iterator
from textwrap import dedent
from typing import Any

from pydantic import Field

from retasc.models.inputs.base import InputBase


class Variables(InputBase):
    """
    Template variables.
    """

    variables: dict[str, Any] = Field(
        description=dedent("""
            Template variables. Example:
              { date: "2027-06-01") }
        """).strip()
    )

    def values(self, context) -> Iterator[dict]:
        yield self.variables

    def report_vars(self, values: dict) -> dict:
        return {"variables": {k: repr(v) for k, v in values.items()}}
