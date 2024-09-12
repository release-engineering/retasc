# SPDX-License-Identifier: GPL-3.0-or-later
from .rule import PrerequisiteRule
from .schedule import PrerequisiteSchedule

# https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions-with-callable-discriminator
type Prerequisite = PrerequisiteSchedule | PrerequisiteRule
