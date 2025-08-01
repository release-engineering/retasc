# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date

from pytest import fixture
from requests import Session

from retasc.product_pages_api import (
    PHASE_IDS,
    Phase,
    ProductPagesApi,
    ProductPagesScheduleTask,
)

PP_URL = "https://product_pages.example.com"

RELEASES = [
    {"shortname": "release-1", "phase": PHASE_IDS[Phase.CONCEPT]},
    {"shortname": "release-2", "phase": PHASE_IDS[Phase.LAUNCH]},
    {"shortname": "release-3", "phase": PHASE_IDS[Phase.MAINTENANCE]},
]


@fixture
def pp_api():
    return ProductPagesApi(PP_URL, session=Session())


def test_phase_enum_values():
    """Test that Phase enum contains all expected phase values."""
    expected_phases = {
        "Concept",
        "Planning",
        "Planning / Development / Testing",
        "CI / CD",
        "Development",
        "Development / Testing",
        "Testing",
        "Exception",
        "Launch",
        "Maintenance",
        "Unsupported",
    }
    actual_phases = {phase.value for phase in Phase}
    assert actual_phases == expected_phases


def test_active_releases(pp_api, requests_mock):
    requests_mock.get(f"{PP_URL}/releases/", json=RELEASES)
    resp = pp_api.active_releases(
        "example_product", min_phase=Phase.CONCEPT, max_phase=Phase.LAUNCH
    )
    assert resp == ["release-1", "release-2"]

    req = requests_mock.request_history[0]
    assert req.qs.get("product__shortname") == ["example_product"]

    resp = pp_api.active_releases(
        "example_product", min_phase=Phase.LAUNCH, max_phase=Phase.LAUNCH
    )
    assert resp == ["release-2"]


def test_active_releases_with_different_phases(pp_api, requests_mock):
    requests_mock.get(f"{PP_URL}/releases/", json=RELEASES)
    resp = pp_api.active_releases(
        "example_product", min_phase=Phase.PLANNING, max_phase=Phase.MAINTENANCE
    )
    assert resp == ["release-2", "release-3"]

    req = requests_mock.request_history[0]
    assert req.qs.get("product__shortname") == ["example_product"]


def test_release_schedules(pp_api, requests_mock):
    schedules = [
        {
            "name": "task1",
            "slug": "rhel.task1",
            "date_start": "2024-10-01",
            "date_finish": "2024-10-02",
            "draft": False,
        },
        {
            "name": "task2",
            "slug": "rhel.task2",
            "date_start": "2024-11-20",
            "date_finish": "2024-11-21",
            "draft": False,
        },
        {
            "name": "task3",
            "slug": "rhel.task3",
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
            slug="rhel.task1",
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 2),
        ),
        ProductPagesScheduleTask(
            name="task2",
            slug="rhel.task2",
            start_date=date(2024, 11, 20),
            end_date=date(2024, 11, 21),
        ),
        ProductPagesScheduleTask(
            name="task3",
            slug="rhel.task3",
            start_date=date(2024, 11, 21),
            end_date=date(2024, 11, 22),
            is_draft=True,
        ),
    ]
