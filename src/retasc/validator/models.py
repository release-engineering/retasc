from typing import List, Optional

from pydantic import BaseModel


class Subtask(BaseModel):
    template: str


class JiraIssue(BaseModel):
    template: str
    subtasks: list[Subtask] | None = None


class Prerequisites(BaseModel):
    pp_schedule_item_name: str
    days_before_or_after: int
    dependent_rules: list[str]


class Rule(BaseModel):
    name: str
    prerequisites: Prerequisites
    jira_issues: list[JiraIssue]
