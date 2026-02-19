import logging
from functools import cached_property
from unittest.mock import ANY

from atlassian import Jira
from opentelemetry import trace
from requests import Session

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class JiraClient:
    """
    Jira Client Wrapper
    """

    def __init__(
        self,
        api_url: str,
        *,
        token: str | None = None,
        session: Session,
        timeout: int | tuple[int, int] | None = None,
        username: str | None = None,
        password: str | None = None,
        cloud: bool = False,
    ):
        self.api_url = api_url
        self.jira = Jira(
            url=api_url,
            username=username,
            password=password,
            token=token,
            session=session,
            cloud=cloud,
        )
        # Override timeout separately, because Jira constructor forces the
        # value to be an int.
        self.jira.timeout = timeout  # type: ignore

    @cached_property
    def current_user_key(self) -> str:
        """
        Get the current user's account ID.
        """
        user = self.jira.myself()
        if isinstance(user, dict) and isinstance(user.get("key"), str):
            return user["key"]

        raise RuntimeError(f"Unexpected response: {user!r}")

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
            return self.jira.jql_get_list_of_tickets(jql, fields=fields)  # type: ignore
        return self.jira.jql_get_list_of_tickets(jql)

    @tracer.start_as_current_span("JiraClient.get_issues")
    def get_issue(
        self, issue_key: str, *, fields: str | dict, expand: str | None = None
    ) -> dict:
        """
        Get a Jira issue.
        """

        data = self.jira.issue(issue_key, fields=fields, expand=expand)
        if isinstance(data, dict):
            return data

        raise RuntimeError(f"Unexpected response: {data}")

    @tracer.start_as_current_span("JiraClient.add_comment")
    def add_comment(self, issue_key: str, comment: str) -> dict:
        """
        Add a comment to a Jira issue.

        :param issue_key: The key of the Jira issue to comment on.
        :param comment: The comment text to add.
        :return: dict containing the comment metadata (id, body, etc.)
        """
        logger.info("Adding comment to Jira issue %r", issue_key)
        data = self.jira.issue_add_comment(issue_key, comment)
        if isinstance(data, dict):
            return data

        raise RuntimeError(f"Unexpected response: {data!r}")

    @tracer.start_as_current_span("JiraClient.get_issue_transitions")
    def get_issue_transitions(self, issue_key: str) -> list[dict]:
        """
        Get available transitions for a Jira issue.

        :param issue_key: The key of the Jira issue.
        :return: list of dicts with keys: name, id, to
        """
        data = self.jira.get_issue_transitions(issue_key)
        if isinstance(data, list):
            return data

        raise RuntimeError(f"Unexpected response: {data!r}")

    @tracer.start_as_current_span("JiraClient.transition_issue")
    def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """
        Transition a Jira issue using a transition ID.

        :param issue_key: The key of the Jira issue.
        :param transition_id: The ID of the transition to execute.
        """
        self.jira.set_issue_status_by_transition_id(issue_key, transition_id)

    @tracer.start_as_current_span("JiraClient.get_issue_comments")
    def get_issue_comments(self, issue_key: str) -> dict:
        """
        Get all comments from a Jira issue.

        :param issue_key: The key of the Jira issue.
        :return: dict with structure: {"comments": [...]}
        """
        data = self.jira.issue_get_comments(issue_key)
        if isinstance(data, dict):
            return data

        raise RuntimeError(f"Unexpected response: {data!r}")


class DryRunJiraClient(JiraClient):
    def edit_issue(
        self, issue_key: str, fields: dict, notify_users: bool = True
    ) -> None:
        # Skip modifying issues in dry-run mode.
        pass

    def create_issue(self, fields: dict) -> dict:
        # Skip creating issues in dry-run mode and return dummy data.
        return {"key": "DRYRUN", "fields": {"resolution": None, **fields}}

    def add_comment(self, issue_key: str, comment: str) -> dict:
        # Skip adding comments in dry-run mode and return dummy data.
        return {"id": "1", "body": comment}

    def get_issue_transitions(self, issue_key: str) -> list[dict]:
        # Return a catch-all transition so status updates never fail in dry-run.
        return [{"id": "0", "name": "Dry Run", "to": ANY}]

    def transition_issue(self, issue_key: str, transition_id: str) -> None:
        # Skip transitioning issues in dry-run mode.
        pass

    def get_issue_comments(self, issue_key: str) -> dict:
        # Skip fetching comments in dry-run mode and return empty list.
        return {"comments": []}
