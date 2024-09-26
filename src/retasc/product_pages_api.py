# SPDX-License-Identifier: GPL-3.0-or-later
"""
Production Pages API
"""

from datetime import date
from functools import cache

from retasc import requests_session


class ProductPagesApi:
    """
    Product Pages API Client
    """

    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip("/")
        self.session = requests_session.requests_session()

    @cache
    def active_releases(self, product_shortname: str) -> list[str]:
        """Gets list of active release names."""
        opt = {
            "product__shortname": product_shortname,
            "phase__lt": "Unsupported",
            "fields": "shortname",
        }
        url = f"{self.api_url}/releases/"
        res = self.session.get(url, params=opt)
        res.raise_for_status()
        data = res.json()
        return [item["shortname"] for item in data]

    @cache
    def release_schedules(self, release_short_name: str) -> dict[str, date]:
        """
        Gets schedules for given release.

        :return: dict with schedule name as key and start date as value
        """
        url = f"{self.api_url}/releases/{release_short_name}/schedule-tasks"
        res = self.session.get(url, params={"fields": "name,date_start"})
        res.raise_for_status()
        data = res.json()
        return {item["name"]: date.fromisoformat(item["date_start"]) for item in data}
