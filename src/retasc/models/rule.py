# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import BaseModel, Field

from .jira_issue import JiraIssueTemplate
from .prerequisites import Prerequisite

SCHEMA_VERSION = 1


class Rule(BaseModel):
    """Rule for creating/managing Jira issues based on prerequisites."""

    version: int = Field(
        description=f"The version of the rule schema. The latest version is {SCHEMA_VERSION}."
    )
    name: str = Field(description="The name of the rule.")
    prerequisites: list[Prerequisite] = Field(
        description="The prerequisites for the rule."
    )
    jira_issues: list[JiraIssueTemplate] = Field(
        description="The jira issues to create and manager for the rule."
    )
    products: list[str] = Field(
        description="Affected Product Pages product short names",
        default_factory=lambda: ["rhel"],
    )
