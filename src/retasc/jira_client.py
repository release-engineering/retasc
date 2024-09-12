# class stubs
# https://github.com/release-engineering/retasc/pull/56
from dataclasses import dataclass


@dataclass(frozen=True)
class JiraClient:
    url: str
    token: str

    def search(self, jql: str, fields=None, limit=None) -> list[dict]:
        return []
