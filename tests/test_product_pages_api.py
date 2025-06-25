# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date

from pytest import fixture
from requests import Session

from retasc.product_pages_api import ProductPagesApi, ProductPagesScheduleTask

PP_URL = "https://product_pages.example.com"


@fixture
def pp_api():
    return ProductPagesApi(PP_URL, session=Session())


def test_active_releases(pp_api, requests_mock):
    releases = [{"shortname": "example-1"}]
    requests_mock.get(f"{PP_URL}/releases/", json=releases)
    resp = pp_api.active_releases(
        "example_product", min_phase="Concept", max_phase="Launch"
    )
    assert resp == ["example-1"]

    req = requests_mock.request_history[0]
    assert req.qs.get("product__shortname") == ["example_product"]
    assert req.qs.get("phase__gte") == ["concept"]
    assert req.qs.get("phase__lte") == ["launch"]


def test_release_schedules(pp_api, requests_mock):
    schedules = [
        {
            "name": "task1",
            "date_start": "2024-10-01",
            "date_finish": "2024-10-02",
            "draft": False,
        },
        {
            "name": "task2",
            "date_start": "2024-11-20",
            "date_finish": "2024-11-21",
            "draft": False,
        },
        {
            "name": "task3",
            "date_start": "2024-11-21",
            "date_finish": "2024-11-22",
            "draft": True,
        },
    ]
    requests_mock.get(
        f"{PP_URL}/releases/example_product/schedule-tasks",
        json=schedules,
    )
    resp = pp_api.release_schedules("example_product")
    assert resp == [
        ProductPagesScheduleTask(
            name="task1",
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 2),
        ),
        ProductPagesScheduleTask(
            name="task2",
            start_date=date(2024, 11, 20),
            end_date=date(2024, 11, 21),
        ),
        ProductPagesScheduleTask(
            name="task3",
            start_date=date(2024, 11, 21),
            end_date=date(2024, 11, 22),
            is_draft=True,
        ),
    ]
