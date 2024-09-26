# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date

from pytest import fixture

from retasc.product_pages_api import ProductPagesApi

PP_URL = "https://product_pages.example.com/api/latest"


@fixture
def pp_api():
    return ProductPagesApi(PP_URL)


def test_active_releases(pp_api, requests_mock):
    releases = [{"shortname": "example-1"}, {"shortname": "example-2"}]
    requests_mock.get(f"{PP_URL}/releases/", json=releases)
    resp = pp_api.active_releases("example_product")
    assert resp == ["example-1", "example-2"]

    req = requests_mock.request_history[0]
    assert req.qs.get("product__shortname") == ["example_product"]


def test_release_schedules(pp_api, requests_mock):
    schedules = [
        {"name": "task1", "date_start": "2024-10-01"},
        {"name": "task2", "date_start": "2024-11-20"},
    ]
    requests_mock.get(
        f"{PP_URL}/releases/example_product/schedule-tasks",
        json=schedules,
    )
    resp = pp_api.release_schedules("example_product")
    assert resp == {"task1": date(2024, 10, 1), "task2": date(2024, 11, 20)}
