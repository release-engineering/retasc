from pydantic import BaseModel
from typing import List, Optional

class Subtask(BaseModel):
    template: str

class JiraIssue(BaseModel):
    template: str
    subtasks: Optional[List[Subtask]] = None

class Prerequisites(BaseModel):
    pp_schedule_item_name: str
    days_before_or_after: int
    dependent_rules: List[str]

class Rule(BaseModel):
    name: str
    prerequisites: Prerequisites
    jira_issues: List[JiraIssue]
