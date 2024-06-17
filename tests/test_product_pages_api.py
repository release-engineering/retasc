# SPDX-License-Identifier: GPL-3.0+
from retasc.product_pages_api import ProductPagesApi
import requests_mock
from pytest import fixture

PP_URL = "https://product_pages.example.com"
PP_API = ProductPagesApi(PP_URL)
test_prod = "rhscl"
test_release = "rhscl-3-8"

@fixture
def pp_api():
    return ProductPagesApi(PP_URL)

# release_url = PP_API.api_url_releases()

def request_assertion(pp_api,prod_or_release, method_under_test, url, res, **kwargs):
    method_to_eval = getattr(pp_api, method_under_test)

    with requests_mock.Mocker() as m:
        m.get(url, json=res)
        if prod_or_release == "product":
            resp = method_to_eval(test_prod)
        elif prod_or_release == "release" and kwargs:
            resp = method_to_eval(test_release, **kwargs)
        else:
            resp = method_to_eval(test_release)
        assert len(m.request_history) == 1 
    assert resp == res

def test_get_pp_url_info(pp_api):
    assert pp_api.api_url == PP_URL
    assert pp_api.api_url_releases() == PP_URL+"/releases/"

def test_active_releases(pp_api):
    test_res = [
        {
            "shortname": "rhscl-3-8",
            "product_shortname": test_prod,
            "ga_date": "2021-11-15",
            "phase_display": "Maintenance"
        }
    ]
    default_fields = "shortname,product_shortname,ga_date,phase_display"
    expected_url = f"{pp_api.api_url_releases()}?product__shortname={test_prod}&phase__lt=Unsupported&fields={default_fields}"
    #test all default parameters for ProductPagesApi.active_releases, url should has all default fields
    request_assertion(pp_api, "product", "active_releases", expected_url, test_res)


def test_release_schedules_with_default(pp_api):
    test_res = [
        {
            "date_finish": "2021-05-10",
            "date_start": "2021-03-08",
            "flags": ["phase"],
            "name": "Planning Phase",
        }
    ]
    default_fields = "release_shortname,name,slug,date_start,date_finish,flags"
    expected_url = f"{pp_api.api_url_releases()}{test_release}/schedule-tasks?fields={default_fields}"
    request_assertion(pp_api, "release", "release_schedules", expected_url, test_res)


def test_release_schedules_by_search_query(pp_api):
    default_fields = "release_shortname,name,slug,date_start,date_finish,flags"
    test_release = "rhscl-3-8"
    test_res = [
        {
            "date_finish": "2021-04-08",
            "date_start": "2021-03-25",
            "name": "Initial configuration for RHSCL 3.8",
            "date_start": "2021-09-27",
            "name": "File ticket for GA -  RC Compose",
            "release_shortname": "rhscl-3-8",
        }
    ]

    # test ProductPagesApi.test_release_schedules_by_search_query search by flags
    expected_url = f"{pp_api.api_url_releases()}{test_release}/schedule-tasks?flags_or__in=rcm,releng,exd,sp&fields={default_fields}"
    request_assertion(pp_api, "release", "release_schedules", expected_url, test_res,  **{"flags_or__in": "rcm,releng,exd,sp"})

    expected_url = f"{pp_api.api_url_releases()}{test_release}/schedule-tasks?flags_and__in=sp&fields={default_fields}"
    request_assertion(pp_api, "release", "release_schedules", expected_url, test_res,  **{"flags_and__in": "sp"})

    expected_url = f"{pp_api.api_url_releases()}{test_release}/schedule-tasks?flags_and__in=sp,ga&fields=name"
    request_assertion(pp_api, "release", "release_schedules", expected_url, test_res, **{"flags_and__in": "sp,ga", "fields":"name"})

    # test ProductPagesApi.test_release_schedules_by_search_query search by name
    expected_url = f"{pp_api.api_url_releases()}{test_release}/schedule-tasks?name__regex=EOL Date&fields={default_fields}"
    request_assertion(pp_api, "release", "release_schedules", expected_url, test_res, **{"name__regex": "EOL Date"})

def test_get_all_active_releases_tasks_for_product(pp_api):
    test_prod = "rhscl"
    releases_res = [
        {
            "shortname": "rhscl-3-8",
            "product_shortname": test_prod,
            "ga_date": "2021-11-15",
            "phase_display": "Maintenance",
        },
        {
            "shortname": "rhscl-3-9",
            "product_shortname": test_prod,
            "ga_date": "2022-11-15",
            "phase_display": "Maintenance",
        }
    ]
    tasks_res = [
        {
            "date_finish": "2021-05-10",
            "date_start": "2021-03-08",
            "flags": ["phase"],
            "name": "Planning Phase",
        }
    ]
    res = {releases_res[0]["shortname"]: tasks_res, releases_res[1]["shortname"]: tasks_res}
    with requests_mock.Mocker() as m:
        m.get(f"{pp_api.api_url_releases()}?product__shortname={test_prod}", json=releases_res)
        m.get(
            f"{pp_api.api_url_releases()}{releases_res[0]["shortname"]}/schedule-tasks",
            json=tasks_res,
        )
        m.get(
            f"{pp_api.api_url_releases()}{releases_res[1]["shortname"]}/schedule-tasks",
            json=tasks_res,
        )
        resp = pp_api.get_all_active_releases_tasks_for_product(test_prod)
    assert resp == res
