# SPDX-License-Identifier: GPL-3.0-or-later
from pytest import fixture

from retasc.product_pages_api import ProductPagesApi

PP_URL = "https://product_pages.example.com"
PP_API = ProductPagesApi(PP_URL)
TEST_PRODUCT = "rhscl"
TEST_RELEASE = "rhscl-3-8"


@fixture
def pp_api():
    return ProductPagesApi(PP_URL)


def test_get_pp_url_info(pp_api):
    assert pp_api.api_url == PP_URL
    assert pp_api.api_url_releases() == PP_URL + "/releases/"


def test_active_releases(pp_api, requests_mock):
    test_res = [
        {
            "shortname": "rhscl-3-8",
            "product_shortname": TEST_PRODUCT,
            "ga_date": "2021-11-15",
            "phase_display": "Maintenance",
        }
    ]
    default_fields = "shortname,product_shortname,ga_date,phase_display"
    requests_mock.get(pp_api.api_url_releases(), json=test_res)
    resp = pp_api.active_releases(TEST_PRODUCT)
    assert len(requests_mock.request_history) == 1
    req = requests_mock.request_history[0]
    assert req.qs.get("product__shortname") == [TEST_PRODUCT]
    assert req.qs.get("fields") == [default_fields]
    assert resp == test_res


def test_release_schedules_with_default(pp_api, requests_mock):
    test_res = [
        {
            "date_finish": "2021-05-10",
            "date_start": "2021-03-08",
            "flags": ["phase"],
            "name": "Planning Phase",
        }
    ]
    default_fields = "release_shortname,name,slug,date_start,date_finish,flags"
    requests_mock.get(
        pp_api.api_url_release_schedule_tasks(TEST_RELEASE), json=test_res
    )
    resp = pp_api.release_schedules(TEST_RELEASE)
    assert len(requests_mock.request_history) == 1
    req = requests_mock.request_history[0]
    assert req.qs.get("fields") == [default_fields]
    assert resp == test_res


def test_release_schedules_by_search_query(pp_api, requests_mock):
    default_fields = "release_shortname,name,slug,date_start,date_finish,flags"
    test_res = [
        {
            "date_finish": "2021-04-08",
            "date_start": "2021-09-27",
            "name": "File ticket for GA -  RC Compose",
            "release_shortname": "rhscl-3-8",
        }
    ]

    # test ProductPagesApi.test_release_schedules_by_search_query search by flags
    # use flags_or__in to search
    requests_mock.get(
        pp_api.api_url_release_schedule_tasks(TEST_RELEASE), json=test_res
    )
    resp = pp_api.release_schedules(
        TEST_RELEASE, **{"flags_or__in": "rcm,releng,exd,sp"}
    )
    req = requests_mock.request_history[0]
    assert req.qs.get("flags_or__in") == ["rcm,releng,exd,sp"]
    assert req.qs.get("fields") == [default_fields]
    assert resp == test_res

    # use flags_and__in to search
    requests_mock.reset()
    resp = pp_api.release_schedules(TEST_RELEASE, **{"flags_and__in": "sp"})
    req = requests_mock.request_history[0]
    assert req.qs.get("flags_and__in") == ["sp"]
    assert resp == test_res

    # use flags_and__in and field to narrow down the search
    requests_mock.reset()
    resp = pp_api.release_schedules(
        TEST_RELEASE, **{"flags_and__in": "sp,ga", "fields": "name"}
    )
    req = requests_mock.request_history[0]
    assert req.qs.get("flags_and__in") == ["sp,ga"]
    assert req.qs.get("fields") == ["name"]
    assert resp == test_res

    # Search by name regex
    requests_mock.reset()
    resp = pp_api.release_schedules(TEST_RELEASE, **{"name__regex": "eol date"})
    req = requests_mock.request_history[0]
    assert req.qs.get("name__regex") == ["eol date"]
    assert resp == test_res


def test_active_release_schedules_for_product(pp_api, requests_mock):
    releases_res = [
        {
            "shortname": "rhscl-3-8",
            "product_shortname": TEST_PRODUCT,
            "ga_date": "2021-11-15",
            "phase_display": "Maintenance",
        },
        {
            "shortname": "rhscl-3-9",
            "product_shortname": TEST_PRODUCT,
            "ga_date": "2022-11-15",
            "phase_display": "Maintenance",
        },
    ]
    tasks_res = [
        {
            "date_finish": "2021-05-10",
            "date_start": "2021-03-08",
            "flags": ["phase"],
            "name": "Planning Phase",
        }
    ]
    res = {
        releases_res[0]["shortname"]: tasks_res,
        releases_res[1]["shortname"]: tasks_res,
    }

    requests_mock.get(pp_api.api_url_releases(), json=releases_res)
    requests_mock.get(
        f"{pp_api.api_url_releases()}{releases_res[0]["shortname"]}/schedule-tasks",
        json=tasks_res,
    )
    requests_mock.get(
        f"{pp_api.api_url_releases()}{releases_res[1]["shortname"]}/schedule-tasks",
        json=tasks_res,
    )

    resp = pp_api.active_release_schedules_for_product(TEST_PRODUCT)
    assert resp == res
