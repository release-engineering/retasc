# SPDX-License-Identifier: GPL-3.0-or-later

from requests.exceptions import RequestException

from retasc.models.http_common import HttpBase, render_template_dict, render_templates
from retasc.models.prerequisites.base import PrerequisiteBase
from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.release_rule_state import ReleaseRuleState


class PrerequisiteHttp(HttpBase, PrerequisiteBase):
    """
    Make an HTTP request.

    Raises an error if the request fails due to connection error, timeout, SSL
    issues, etc.

    Adds http_response template parameter (the type is requests.Response).
    """

    def update_state(self, context) -> ReleaseRuleState:
        url = context.template.render(self.url)
        headers = render_template_dict(self.headers, context)
        params = render_template_dict(self.params, context)
        data = render_templates(self.data, context)

        try:
            context.template.params["http_response"] = context.session.request(
                self.method, url, params=params, json=data, headers=headers
            )
        except RequestException as e:
            raise PrerequisiteUpdateStateError(f"HTTP request failed: {e}")

        return ReleaseRuleState.Completed
