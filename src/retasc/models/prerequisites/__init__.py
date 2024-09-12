# SPDX-License-Identifier: GPL-3.0-or-later
from .condition import PrerequisiteCondition
from .jira_issue import PrerequisiteJiraIssue
from .rule import PrerequisiteRule
from .schedule import PrerequisiteSchedule
from .target_date import PrerequisiteTargetDate

type Prerequisite = (
    PrerequisiteCondition
    | PrerequisiteJiraIssue
    | PrerequisiteRule
    | PrerequisiteSchedule
    | PrerequisiteTargetDate
)
