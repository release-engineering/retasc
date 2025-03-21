# SPDX-License-Identifier: GPL-3.0-or-later
from retasc.models.inputs.jira_issues import JiraIssues
from retasc.models.inputs.product_pages_releases import ProductPagesReleases

type Input = ProductPagesReleases | JiraIssues
