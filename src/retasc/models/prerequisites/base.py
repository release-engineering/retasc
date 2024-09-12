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
        return []

    def state(self, context) -> ReleaseRuleState:
        return ReleaseRuleState.Pending

    def update_params(self, params: dict, context):
        """Update template parameters"""
