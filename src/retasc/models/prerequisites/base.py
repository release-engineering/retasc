# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import BaseModel

from retasc.models.release_rule_state import ReleaseRuleState


class PrerequisiteBase(BaseModel):
    """Base class for rule prerequisites."""

    class Config:
        # Forbid extra attributes during model initialization.
        # This makes union types work correctly.
        extra = "forbid"

        frozen = True

    def validation_errors(self, rules) -> list[str]:
        """Return validation errors if any."""
        return []

    def update_state(self, context) -> ReleaseRuleState:
        """Update template variables if needed and returns current state."""
        raise NotImplementedError()

    def section_name(self) -> str:
        """Section name in report."""
        raise NotImplementedError()
