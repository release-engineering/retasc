# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict


class InputBase(BaseModel):
    """Base class for rule inputs."""

    model_config = ConfigDict(
        frozen=True,
        # Forbid extra attributes during model initialization.
        # This makes union types work correctly.
        extra="forbid",
    )

    def values(self, context) -> Iterator[dict]:
        """Yield input dicts"""
        raise NotImplementedError()
