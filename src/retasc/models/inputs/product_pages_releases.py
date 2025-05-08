# SPDX-License-Identifier: GPL-3.0-or-later
import re
from collections.abc import Iterator

from pydantic import Field

from retasc.models.inputs.base import InputBase

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
    """

    product: str = Field(description="Product short name in Product Pages")

    def values(self, context) -> Iterator[dict]:
        releases = context.pp.active_releases(self.product)
        for release in releases:
            major, minor = parse_version(release)
            data = {
                "product": self.product,
                "release": release,
                "major": major,
                "minor": minor,
                "jira_label_suffix": f"-{release}",
            }
            yield data

    def report_vars(self, values: dict) -> dict:
        return {"release": values["release"]}
