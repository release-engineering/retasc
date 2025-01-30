import logging

from atlassian import Jira
from opentelemetry import trace
from requests import Session

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class JiraClient:
    """
    Jira Client Wrapper
    """

    def __init__(self, api_url: str, *, token: str, session: Session):
        self.api_url = api_url
        self.jira = Jira(
            url=api_url,
            token=token,
            session=session,
        )

    @tracer.start_as_current_span("JiraClient.edit_issue")
    def edit_issue(
        self, issue_key: str, fields: dict, notify_users: bool = True
    ) -> None:
        """
        Updates a Jira issue with the provided fields.

        :param issue_key: The key of the Jira issue to update.
        :param fields: A dictionary of fields to update in the issue.
                    example:
                        fields = {
                            'project': {'key': 'RHELWF'},
                            'summary': '[ReTaSC] Default summary',
                            'description': 'Default description - please update this description.',
                            'issuetype': {'name': 'Story'},
                            'priority': {'name':'Normal'}
                        }
        :return:
        :if not found: requests.exceptions.HTTPError: Issue Does Not Exist
        """

        logger.info("Updating Jira issue %r with fields: %r", issue_key, fields)
        base_url = self.jira.resource_url("issue")
        url = f"{base_url}/{issue_key}"
        self.jira.put(
            url, data={"fields": fields}, params={"notifyUsers": notify_users}
        )

    @tracer.start_as_current_span("JiraClient.create_issue")
    def create_issue(self, fields: dict) -> dict:
        """
        Create a new Jira issue
        """
        logger.info("Creating new Jira issue with fields: %r", fields)

        data = self.jira.create_issue(fields)
        if isinstance(data, dict):
            return data

        raise RuntimeError(f"Unexpected response: {data!r}")

    @tracer.start_as_current_span("JiraClient.search_issues")
    def search_issues(self, jql: str, fields: list[str] | None = None) -> list:
        """
        Search Issues by JQL

        :param jql: string: like "project = DEMO AND status NOT IN (Closed, Resolved) ORDER BY issuekey"
        """

        if fields:
            return self.jira.jql_get_list_of_tickets(jql, fields=fields)
        return self.jira.jql_get_list_of_tickets(jql)

    @tracer.start_as_current_span("JiraClient.get_issues")
    def get_issue(self, issue_key: str) -> dict:
        """
        Get a Jira issue.
        """

        data = self.jira.issue(issue_key)
        if isinstance(data, dict):
            return data

        raise RuntimeError(f"Unexpected response: {data}")


class DryRunJiraClient(JiraClient):
    def edit_issue(
        self, issue_key: str, fields: dict, notify_users: bool = True
    ) -> None:
        # Skip modifying issues in dry-run mode.
        pass

    def create_issue(self, fields: dict) -> dict:
        # Skip creating issues in dry-run mode and return dummy data.
        return {"key": "DRYRUN", "fields": {"resolution": None, **fields}}
