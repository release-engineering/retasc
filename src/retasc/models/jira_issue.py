# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import BaseModel, Field


class JiraIssueTemplate(BaseModel):
    """Jira issue template with optional sub-tasks."""

    id: str = Field(description="Unique identifier for the issue.")
    template: str = Field(description="The template file for the jira issue.")
    subtasks: list["JiraIssueTemplate"] = Field(
        default=[], description="The subtasks for the jira issue."
    )

    @property
    def label(self):
        return f"retasc-id-{self.id}"
