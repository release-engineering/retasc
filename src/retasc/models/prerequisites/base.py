# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import BaseModel, ConfigDict

import retasc.models.config
from retasc.models.release_rule_state import ReleaseRuleState


class PrerequisiteBase(BaseModel):
    """Base class for rule prerequisites."""

    model_config = ConfigDict(
        frozen=True,
        # Forbid extra attributes during model initialization.
        # This makes union types work correctly.
        extra="forbid",
    )

    def validation_errors(
        self, rules, config: retasc.models.config.Config
    ) -> list[str]:
        """Return validation errors if any."""
        return []

    def update_state(self, context) -> ReleaseRuleState:
        """
        Called by parent rule to update any state and template variables.

        Called only if no previous prerequisite returned Pending state.

        Returns new prerequisite state.
        """
        raise NotImplementedError()
