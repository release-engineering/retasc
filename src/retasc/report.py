# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field

from opentelemetry import trace
from requests.exceptions import RequestException

tracer = trace.get_tracer(__name__)


@dataclass
class Report:
    data: dict = field(default_factory=dict)
    current_sections: list = field(default_factory=list)
    current_data: dict = field(default_factory=dict)
    current_list: list | None = None
    jira_issues: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.current_data = self.data

    def print(self, text: str):
        indent = "  " * len(self.current_sections)
        print(f"{indent}{text.replace('\n', f'{indent}\n')}")

    @contextmanager
    def section(self, parent: str, type: str, name: str):
        section = f"{type}({name!r})"
        self.print(section)
        self.current_sections.append(section)
        prev_data = self.current_data

        item_list = self.current_data.setdefault(parent, [])
        self.current_data = {"type": type}
        item_list.append(self.current_data)

        with tracer.start_as_current_span(f"section:{section}"):
            yield

        self.current_data = prev_data
        self.current_sections.pop()

    def set(self, key, value):
        # Print the value only if it's not already in the current section name
        if not self.current_sections or f"({value!r})" not in self.current_sections[-1]:
            self.print(f"{key}: {value}")
        self.current_data[key] = deepcopy(value)

    def add_error(self, error: str):
        self.set("error", f"❌ {error}")
        label = "\n".join(f"{'  ' * i}{s}" for i, s in enumerate(self.current_sections))
        indent = "  " * len(self.current_sections)
        self.errors.append(f"{label}\n{indent}{error}")

    def add_request_error(self, e: RequestException):
        msg = [repr(e)]
        if e.response is not None:
            msg.extend(
                [
                    f"status={e.response.status_code!r}",
                    f"body={e.response.text!r}",
                ]
            )
        if e.request is not None:
            msg.append(f"url={e.request.url!r}")
        self.add_error(" ".join(msg))
