# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class Report:
    data: dict = field(default_factory=dict)
    current_sections: list = field(default_factory=list)
    current_data: dict = field(default_factory=dict)
    jira_issues: dict = field(default_factory=dict)

    def __post_init__(self):
        self.current_data = self.data

    def print(self, text: str):
        indent = "  " * len(self.current_sections)
        print(f"{indent}{text.replace('\n', f'{indent}\n')}")

    @contextmanager
    def section(self, state):
        self.print(str(state))
        self.current_sections.append(state)
        prev_data = self.current_data
        self.current_data = self.current_data.setdefault(state, {})

        yield

        self.current_data = prev_data
        self.current_sections.pop()

    def set(self, key, value):
        self.print(f"{key}: {value}")
        self.current_data[key] = deepcopy(value)
