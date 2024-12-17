# SPDX-License-Identifier: GPL-3.0-or-later
import json
import re
from collections.abc import Iterator

from pydantic import Field

from retasc.models.inputs.base import InputBase
from retasc.models.inputs.jira_issues import get_issues

RE_VERSION = re.compile(r"^\w+-(?P<major>\d+)(?:[-.](?P<minor>\d+))?")


def parse_version(release: str) -> tuple[int, int]:
    """
    Parse version numbers (major, minor) from Product Pages release short name.
    """
    match = re.search(RE_VERSION, release)
    if not match:
        return 0, 0

    x = match.groupdict(default=0)
    return int(x["major"]), int(x["minor"])


class ProductPagesReleases(InputBase):
    """
    Releases for a product from Product Pages.

    Adds the following template parameters:
    - product - product short name
    - release - release short name
    - major - major version number
    - minor - minor version number
    - jira_labels - common issue labels from jira_label_templates
    - jira_issues - all issues matching the jira_labels
    """

    product: str = Field(description="Product short name in Product Pages")
    jira_label_templates: list[str] = Field(
        description=(
            "Label templates that need to be set for the managed issues in Jira."
            '\nExample: ["retasc-managed", "retasc-managed-{{ release }}"]'
        ),
        default_factory=list,
    )

    def values(self, context) -> Iterator[dict]:
        releases = context.pp.active_releases(self.product)
        for release in releases:
            major, minor = parse_version(release)
            data = {
                "product": self.product,
                "release": release,
                "major": major,
                "minor": minor,
            }
            labels = [
                context.template.render(template, **data)
                for template in self.jira_label_templates
            ]
            labels = [label for label in labels if label]
            data["jira_labels"] = labels
            jql = " AND ".join(f"labels={json.dumps(label)}" for label in labels)
            data["jira_issues"] = get_issues(jql, context) if jql else {}
            yield data

    def section_name(self, values: dict) -> str:
        return f"ProductPagesRelease({values['release']!r})"
