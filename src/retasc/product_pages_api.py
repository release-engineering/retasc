# SPDX-License-Identifier: GPL-3.0-or-later
"""
Production Pages API
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import cache

from opentelemetry import trace
from requests import Session

tracer = trace.get_tracer(__name__)


class Phase(str, Enum):
    """Available Product Pages release phases."""

    CONCEPT = "Concept"
    PLANNING = "Planning"
    PLANNING_DEVELOPMENT_TESTING = "Planning / Development / Testing"
    CI_CD = "CI / CD"
    DEVELOPMENT = "Development"
    DEVELOPMENT_TESTING = "Development / Testing"
    TESTING = "Testing"
    EXCEPTION = "Exception"
    LAUNCH = "Launch"
    MAINTENANCE = "Maintenance"
    UNSUPPORTED = "Unsupported"


# Copied from PP API /api/v7/schedules/phases/
PHASE_IDS = {
    Phase.CONCEPT: 100,
    Phase.PLANNING: 200,
    Phase.PLANNING_DEVELOPMENT_TESTING: 230,
    Phase.CI_CD: 270,
    Phase.DEVELOPMENT: 300,
    Phase.DEVELOPMENT_TESTING: 350,
    Phase.TESTING: 400,
    Phase.EXCEPTION: 450,
    Phase.LAUNCH: 500,
    Phase.MAINTENANCE: 600,
    Phase.UNSUPPORTED: 1000,
}


@dataclass
class ProductPagesScheduleTask:
    name: str
    slug: str
    start_date: date
    end_date: date
    is_draft: bool = False


class ProductPagesApi:
    """
    Product Pages API Client
    """

    def __init__(self, api_url: str, *, session: Session):
        self.api_url = api_url.rstrip("/")
        self.session = session

    @cache
    @tracer.start_as_current_span("ProductPagesApi.active_releases")
    def active_releases(
        self,
        product_shortname: str,
        min_phase: Phase,
        max_phase: Phase,
    ) -> list[str]:
        """
        Gets list of active release names within the specified phase range.

        :param product_shortname: Product short name
        :param min_phase: Minimum phase (inclusive)
        :param max_phase: Maximum phase (inclusive)
        :return: List of release short names
        """
        opt = {
            "product__shortname": product_shortname,
            "fields": "shortname,phase",
        }
        url = f"{self.api_url}/releases/"
        res = self.session.get(url, params=opt)
        res.raise_for_status()
        data = res.json()
        lower_bound = PHASE_IDS[min_phase]
        upper_bound = PHASE_IDS[max_phase]
        # Product Pages release API does not seem to work with phase__gt and
        # phase__lt parameters.
        return [
            item["shortname"]
            for item in data
            if lower_bound <= item["phase"] <= upper_bound
        ]

    @cache
    @tracer.start_as_current_span("ProductPagesApi.release_schedules")
    def release_schedules(
        self, release_short_name: str
    ) -> list[ProductPagesScheduleTask]:
        """
        Gets schedules for given release.

        :return: dict with schedule name as key and start date as value
        """
        url = f"{self.api_url}/releases/{release_short_name}/schedule-tasks"
        res = self.session.get(
            url, params={"fields": "name,date_start,date_finish,draft,slug"}
        )
        res.raise_for_status()
        data = res.json()
        return [
            ProductPagesScheduleTask(
                name=item["name"],
                slug=item["slug"],
                start_date=date.fromisoformat(item["date_start"]),
                end_date=date.fromisoformat(item["date_finish"]),
                is_draft=item["draft"],
            )
            for item in data
        ]
