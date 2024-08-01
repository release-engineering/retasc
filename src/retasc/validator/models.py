# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class JiraIssue(BaseModel):
    """Represents a Jira issue, which can have subtasks."""

    template: str = Field(description="The template string for the jira issue.")
    subtasks: list["JiraIssue"] = Field(
        default=[], description="The subtasks for the jira issue."
    )


class Prerequisites(BaseModel):
    """Defines the prerequisites needed for a rule."""

    pp_schedule_item_name: str = Field(description="The name of the pp schedule item.")
    days_before_or_after: int = Field(
        description=(
            "The number of days to adjust the schedule relative to the PP schedule item date. "
            "A negative value indicates the number of days before the PP schedule item date, "
            "while a positive value indicates the number of days after the PP schedule item date. "
            "This value helps determine the target date for creating Jira issues."
        ),
    )
    dependent_rules: list[str] = Field(
        default=[],
        description="The dependent rules for the prerequisite schedule item.",
    )


class Rule(BaseModel):
    """Represents a rule which includes prerequisites and Jira issues."""

    version: int = Field(
        description=f"The version of the rule schema. The latest version is {SCHEMA_VERSION}."
    )
    name: str = Field(description="The name of the rule.")
    prerequisites: Prerequisites = Field(description="The prerequisites for the rule.")
    jira_issues: list[JiraIssue] = Field(description="The jira issues for the rule.")
