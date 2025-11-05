# SPDX-License-Identifier: GPL-3.0-or-later
from .condition import PrerequisiteCondition
from .http import PrerequisiteHttp
from .jira_issue import PrerequisiteJiraIssue
from .pipeline_run import PrerequisitePipelineRun
from .rule import PrerequisiteRule
from .schedule import PrerequisiteSchedule
from .target_date import PrerequisiteTargetDate
from .variable import PrerequisiteVariable
from .variable_string import PrerequisiteVariableString

type Prerequisite = (
    PrerequisiteCondition
    | PrerequisiteHttp
    | PrerequisiteJiraIssue
    | PrerequisitePipelineRun
    | PrerequisiteRule
    | PrerequisiteSchedule
    | PrerequisiteTargetDate
    | PrerequisiteVariable
    | PrerequisiteVariableString
)
