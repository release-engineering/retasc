# SPDX-License-Identifier: GPL-3.0-or-later
from .condition import PrerequisiteCondition
from .rule import PrerequisiteRule
from .schedule import PrerequisiteSchedule

# https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions-with-callable-discriminator
type Prerequisite = PrerequisiteCondition | PrerequisiteSchedule | PrerequisiteRule
