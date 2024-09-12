# SPDX-License-Identifier: GPL-3.0-or-later
from enum import IntEnum


class ReleaseRuleState(IntEnum):
    Pending = 0
    InProgress = 1
    Completed = 2
