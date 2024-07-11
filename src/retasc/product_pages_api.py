# SPDX-License-Identifier: GPL-3.0-or-later
"""
Production Pages API
"""

from functools import cache

from retasc import requests_session


class ProductPagesApi:
    """
    Product Pages API Client
    """

    def __init__(self, api_url: str):
        self.api_url = api_url
        self.session = requests_session.requests_session()

    def api_url_releases(self, release_name: str | None = None) -> str:
        return f"{self.api_url.rstrip('/')}/releases/{release_name or ''}"

    def api_url_release_schedule_tasks(self, release_name: str) -> str:
        return f"{self.api_url_releases(release_name)}/schedule-tasks"

    @cache
    def active_releases(
        self,
        product_shortname: str,
        fields: str = "shortname,product_shortname,ga_date,phase_display",
    ) -> list[dict]:
        """
        https://{pp_release_url}?product__shortname={product_shortname}&phase__lt=Unsupported&fields=a,b,c
        The response have the following fields:shortname,product_shortname,ga_date,phase_display
        phase__lt=Unsupported means "any supported phase" (these are less than Unsupported).
        """

        opt = {
            "product__shortname": product_shortname,
            "phase__lt": "Unsupported",
            "fields": fields,
        }
        res = self.session.get(self.api_url_releases(), params=opt)
        res.raise_for_status()
        return res.json()

    @cache
    def release_schedules(
        self,
        release_short_name: str,
        fields: str = "release_shortname,name,slug,date_start,date_finish,flags",
        **kwargs,
    ) -> list[dict]:
        """
        https://{api_url_release_schedule_tasks}/?{kwargs...}
        """
        url = self.api_url_release_schedule_tasks(release_short_name)

        # fields has some default value, can be updated if kwargs has it
        addtional_query = {"fields": fields, **kwargs}

        res = self.session.get(url, params=addtional_query)
        res.raise_for_status()
        return res.json()

    @cache
    def active_release_schedules_for_product(self, product_shortname: str) -> dict:
        """
        Get all release names that are still supported by rest api:
        https://{pp_release_url}?product__shortname={product_shortname}&phase__lt=Unsupported&fields=shortname
        Loop through the releases and get the tasks of it by rest api
        https://{pp_release_url}{release_short_name}/schedule-tasks/fields=name,slug,date_start,date_finish
        """

        releases_list = self.active_releases(product_shortname)
        return {
            r["shortname"]: self.release_schedules(r["shortname"])
            for r in releases_list
        }
