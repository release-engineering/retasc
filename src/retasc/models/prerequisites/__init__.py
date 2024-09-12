# SPDX-License-Identifier: GPL-3.0-or-later
from .rule import PrerequisiteRule
from .schedule import PrerequisiteSchedule

type Prerequisite = PrerequisiteSchedule | PrerequisiteRule
