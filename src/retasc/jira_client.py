import logging

from atlassian import Jira

logger = logging.getLogger(__name__)


class JiraClient:
    """
    Jira Client Wrapper
    """

    def __init__(self, api_url: str, token: str | None = None):
        self.api_url = api_url
        self.jira = Jira(
            url=api_url,
            token=token,
        )


    def api_url_issue(self, issue_key: str | None = None) -> str:
        return f"{self.api_url.rstrip('/')}/rest/api/2/issue/{issue_key or ''}"

    def api_url_create_issue(self) -> str:
        return f"{self.api_url.rstrip('/')}/rest/api/2/issue?updateHistory=false"

    def api_url_edit_issue(self, issue_key: str) -> str:
        return f"{self.api_url.rstrip('/')}/rest/api/2/issue/{issue_key}?notifyUsers=true"

    def edit_issue(self, issue_key: str, fields: dict) -> None:
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
        """

        logger.info(f"Updating Jira issue {issue_key} with fields: {fields}")
        self.jira.edit_issue(issue_key, fields)
        # if not found: requests.exceptions.HTTPError: Issue Does Not Exist

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str,
        fields: dict = {},
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

        issue_dict.update(fields)

        logger.info(f"Creating new Jira issue with fields: {issue_dict}")
        issue = self.jira.create_issue(issue_dict)
        return issue

    def get_issue(self, issue_key: str) -> dict:
        """
        Get a Jira issue.
        """

        issue = self.jira.issue(issue_key)
        return issue
