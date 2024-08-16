import logging

from atlassian import Jira

from retasc.requests_session import requests_session

logger = logging.getLogger(__name__)

DEFAULT_JIRA_URL = "https://issues.redhat.com"


class JiraClient:
    """
    Jira Client Wrapper
    """

    def __init__(self, jira_url: str = DEFAULT_JIRA_URL, token: str | None = None):
        self.jira = Jira(
            url=jira_url,
            timeout=60,
            verify_ssl=True,
            session=requests_session(),
            token=token,
        )

    def update_issue(self, issue_key: str, fields: dict) -> None:
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
        """

        logger.info(f"Updating Jira issue {issue_key} with fields: {fields}")
        self.jira.issue_update(issue_key, fields)
        # if not found: requests.exceptions.HTTPError: Issue Does Not Exist

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str,
        fields: dict | None = None,
    ) -> dict:
        """
        Create a new Jira issue
        """

        issue_dict = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }

        if fields:
            issue_dict.update(fields)

        logger.info(f"Creating new Jira issue with fields: {issue_dict}")
        issue = self.jira.issue_create(issue_dict)
        return issue

    def delete_issue(self, issue_key: str) -> None:
        """
        Delete a Jira issue.
        """

        logger.info(f"Deleting Jira issue: {issue_key}")
        self.jira.delete_issue(issue_key)

    def get_issue(self, issue_key: str) -> dict:
        """
        Get a Jira issue.
        """

        issue = self.jira.issue(issue_key)
        return issue

    def __getattr__(self, name):
        """
        Delegate attribute access to Atlassian Jira
        """

        return getattr(self.jira, name)
