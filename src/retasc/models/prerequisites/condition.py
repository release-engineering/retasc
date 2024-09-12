# SPDX-License-Identifier: GPL-3.0-or-later
from retasc.models.release_rule_state import ReleaseRuleState

from .base import PrerequisiteBase


class PrerequisiteCondition(PrerequisiteBase):
    """Base class for rule prerequisites."""

    condition: str

    def state(self, context) -> ReleaseRuleState:
        is_completed = context.template.evaluate(self.condition)
        if is_completed:
            return ReleaseRuleState.Completed

        context.print(f"--- Condition failed {self.condition!r}: {is_completed!r}")
        return ReleaseRuleState.Pending
