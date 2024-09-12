# class stubs
# https://github.com/release-engineering/retasc/pull/56
from dataclasses import dataclass


class JiraIssue:
    pass


@dataclass
class JiraClient:
    url: str
    token: str

    def search(self, jql: str) -> list[JiraIssue]:
        return []
