# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from importlib_resources import files
from typing import Any, Union, Optional

from otterdog import resources
from otterdog import utils
from otterdog.credentials import Credentials

from .graphql import GraphQLClient
from .rest import RestApi
from .web import WebClient

_ORG_SETTINGS_SCHEMA = json.loads(files(resources).joinpath("schemas/settings.json").read_text())


class GitHubProvider:
    def __init__(self, credentials: Union[Credentials, None]):
        self._credentials = credentials

        self._settings_schema = _ORG_SETTINGS_SCHEMA
        # collect supported rest api keys
        self._settings_restapi_keys = {
            k for k, v in self._settings_schema["properties"].items() if v.get("provider") == "restapi"
        }

        # collect supported web interface keys
        self._settings_web_keys = {
            k for k, v in self._settings_schema["properties"].items() if v.get("provider") == "web"
        }
        # TODO: make this cleaner
        self._settings_web_keys.add("discussion_source_repository_id")

        if credentials is not None:
            self._init_clients()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.close()

    def close(self) -> None:
        if self._credentials is not None:
            self.rest_api.close()

    def _init_clients(self):
        from .rest.auth.token import TokenAuthStrategy

        self.rest_api = RestApi(TokenAuthStrategy(self._credentials.github_token))
        self.web_client = WebClient(self._credentials)
        self.graphql_client = GraphQLClient(self._credentials.github_token)

    def __getstate__(self):
        return (
            self._credentials,
            self._settings_schema,
            self._settings_restapi_keys,
            self._settings_web_keys,
        )

    def __setstate__(self, state):
        (
            self._credentials,
            self._settings_schema,
            self._settings_restapi_keys,
            self._settings_web_keys,
        ) = state
        self._init_clients()

    def get_content(self, org_id: str, repo_name: str, path: str, ref: Optional[str] = None) -> str:
        return self.rest_api.content.get_content(org_id, repo_name, path, ref)

    def update_content(
        self,
        org_id: str,
        repo_name: str,
        path: str,
        content: str,
        message: Optional[str] = None,
    ) -> bool:
        return self.rest_api.content.update_content(org_id, repo_name, path, content, message)

    def get_org_settings(self, org_id: str, included_keys: set[str], no_web_ui: bool) -> dict[str, Any]:
        # first, get supported settings via the rest api.
        required_rest_keys = {x for x in included_keys if x in self._settings_restapi_keys}
        merged_settings = self.rest_api.org.get_settings(org_id, required_rest_keys)

        # second, get settings only accessible via the web interface and merge
        # them with the other settings, unless --no-web-ui is specified.
        if not no_web_ui:
            required_web_keys = {x for x in included_keys if x in self._settings_web_keys}
            if len(required_web_keys) > 0:
                web_settings = self.web_client.get_org_settings(org_id, required_web_keys)
                merged_settings.update(web_settings)

            utils.print_trace(f"merged org settings = {merged_settings}")

        return merged_settings

    def update_org_settings(self, org_id: str, settings: dict[str, Any]) -> None:
        rest_fields = {}
        web_fields = {}

        # split up settings to be updated whether they need be updated
        # via rest api or web interface.
        for k, v in sorted(settings.items()):
            if k in self._settings_restapi_keys:
                rest_fields[k] = v
            elif k in self._settings_web_keys:
                web_fields[k] = v
            else:
                utils.print_warn(f"encountered unknown field '{k}' during update, ignoring")

        # update any settings via the rest api
        if len(rest_fields) > 0:
            self.rest_api.org.update_settings(org_id, rest_fields)

        # update any settings via the web interface
        if len(web_fields) > 0:
            self.web_client.update_org_settings(org_id, web_fields)

    def get_org_workflow_settings(self, org_id: str) -> dict[str, Any]:
        return self.rest_api.org.get_workflow_settings(org_id)

    def update_org_workflow_settings(self, org_id: str, workflow_settings: dict[str, Any]) -> None:
        self.rest_api.org.update_workflow_settings(org_id, workflow_settings)

    def get_org_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        return self.rest_api.org.get_webhooks(org_id)

    def update_org_webhook(self, org_id: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        if len(webhook) > 0:
            self.rest_api.org.update_webhook(org_id, webhook_id, webhook)

    def add_org_webhook(self, org_id: str, data: dict[str, str]) -> None:
        self.rest_api.org.add_webhook(org_id, data)

    def delete_org_webhook(self, org_id: str, webhook_id: int, url: str) -> None:
        self.rest_api.org.delete_webhook(org_id, webhook_id, url)

    def get_repos(self, org_id: str) -> list[str]:
        # filter out repos which are created to work on GitHub Security Advisories
        # they should not be part of the visible configuration
        return list(filter(lambda name: not utils.is_ghsa_repo(name), self.rest_api.org.get_repos(org_id)))

    def get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        return self.rest_api.repo.get_repo_data(org_id, repo_name)

    def get_repo_by_id(self, repo_id: int) -> dict[str, Any]:
        return self.rest_api.repo.get_repo_by_id(repo_id)

    def update_repo(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        if len(data) > 0:
            self.rest_api.repo.update_repo(org_id, repo_name, data)

    def add_repo(
        self,
        org_id: str,
        data: dict[str, str],
        template_repository: Optional[str],
        post_process_template_content: list[str],
        forked_repository: Optional[str],
        fork_default_branch_only: bool,
        auto_init_repo: bool,
    ) -> None:
        self.rest_api.repo.add_repo(
            org_id,
            data,
            template_repository,
            post_process_template_content,
            forked_repository,
            fork_default_branch_only,
            auto_init_repo,
        )

    def delete_repo(self, org_id: str, repo_name: str) -> None:
        self.rest_api.repo.delete_repo(org_id, repo_name)

    async def get_branch_protection_rules(self, org_id: str, repo: str) -> list[dict[str, Any]]:
        return await self.graphql_client.async_get_branch_protection_rules(org_id, repo)

    def update_branch_protection_rule(
        self,
        org_id: str,
        repo_name: str,
        rule_pattern: str,
        rule_id: str,
        data: dict[str, Any],
    ) -> None:
        self.graphql_client.update_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id, data)

    def add_branch_protection_rule(
        self,
        org_id: str,
        repo_name: str,
        repo_node_id: Optional[str],
        data: dict[str, Any],
    ) -> None:
        # in case the repo_id is not available yet, we need to fetch it from GitHub.
        if not repo_node_id:
            repo_data = self.rest_api.repo.get_repo_data(org_id, repo_name)
            repo_node_id = repo_data["node_id"]

        self.graphql_client.add_branch_protection_rule(org_id, repo_name, repo_node_id, data)

    def delete_branch_protection_rule(self, org_id: str, repo_name: str, rule_pattern: str, rule_id: str) -> None:
        self.graphql_client.delete_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id)

    def update_repo_ruleset(self, org_id: str, repo_name: str, ruleset_id: int, ruleset: dict[str, Any]) -> None:
        if len(ruleset) > 0:
            self.rest_api.repo.update_ruleset(org_id, repo_name, ruleset_id, ruleset)

    def add_repo_ruleset(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        self.rest_api.repo.add_ruleset(org_id, repo_name, data)

    def delete_repo_ruleset(self, org_id: str, repo_name: str, ruleset_id: int, name: str) -> None:
        self.rest_api.repo.delete_ruleset(org_id, repo_name, ruleset_id, name)

    def get_repo_webhooks(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        return self.rest_api.repo.get_webhooks(org_id, repo_name)

    def update_repo_webhook(self, org_id: str, repo_name: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        if len(webhook) > 0:
            self.rest_api.repo.update_webhook(org_id, repo_name, webhook_id, webhook)

    def add_repo_webhook(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        self.rest_api.repo.add_webhook(org_id, repo_name, data)

    def delete_repo_webhook(self, org_id: str, repo_name: str, webhook_id: int, url: str) -> None:
        self.rest_api.repo.delete_webhook(org_id, repo_name, webhook_id, url)

    def get_repo_environments(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        return self.rest_api.repo.get_environments(org_id, repo_name)

    def update_repo_environment(self, org_id: str, repo_name: str, env_name: str, env: dict[str, Any]) -> None:
        if len(env) > 0:
            self.rest_api.repo.update_environment(org_id, repo_name, env_name, env)

    def add_repo_environment(self, org_id: str, repo_name: str, env_name: str, data: dict[str, str]) -> None:
        self.rest_api.repo.add_environment(org_id, repo_name, env_name, data)

    def delete_repo_environment(self, org_id: str, repo_name: str, env_name: str) -> None:
        self.rest_api.repo.delete_environment(org_id, repo_name, env_name)

    def get_repo_workflow_settings(self, org_id: str, repo_name: str) -> dict[str, Any]:
        return self.rest_api.repo.get_workflow_settings(org_id, repo_name)

    def update_repo_workflow_settings(self, org_id: str, repo_name: str, workflow_settings: dict[str, Any]) -> None:
        self.rest_api.repo.update_workflow_settings(org_id, repo_name, workflow_settings)

    def get_org_secrets(self, org_id: str) -> list[dict[str, Any]]:
        return self.rest_api.org.get_secrets(org_id)

    def update_org_secret(self, org_id: str, secret_name: str, secret: dict[str, Any]) -> None:
        if len(secret) > 0:
            self.rest_api.org.update_secret(org_id, secret_name, secret)

    def add_org_secret(self, org_id: str, data: dict[str, str]) -> None:
        self.rest_api.org.add_secret(org_id, data)

    def delete_org_secret(self, org_id: str, secret_name: str) -> None:
        self.rest_api.org.delete_secret(org_id, secret_name)

    def get_org_variables(self, org_id: str) -> list[dict[str, Any]]:
        return self.rest_api.org.get_variables(org_id)

    def update_org_variable(self, org_id: str, variable_name: str, variable: dict[str, Any]) -> None:
        if len(variable) > 0:
            self.rest_api.org.update_variable(org_id, variable_name, variable)

    def add_org_variable(self, org_id: str, data: dict[str, str]) -> None:
        self.rest_api.org.add_variable(org_id, data)

    def delete_org_variable(self, org_id: str, variable_name: str) -> None:
        self.rest_api.org.delete_variable(org_id, variable_name)

    def get_repo_secrets(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        return self.rest_api.repo.get_secrets(org_id, repo_name)

    def update_repo_secret(self, org_id: str, repo_name: str, secret_name: str, secret: dict[str, Any]) -> None:
        if len(secret) > 0:
            self.rest_api.repo.update_secret(org_id, repo_name, secret_name, secret)

    def add_repo_secret(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        self.rest_api.repo.add_secret(org_id, repo_name, data)

    def delete_repo_secret(self, org_id: str, repo_name: str, secret_name: str) -> None:
        self.rest_api.repo.delete_secret(org_id, repo_name, secret_name)

    def get_repo_variables(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        return self.rest_api.repo.get_variables(org_id, repo_name)

    def update_repo_variable(self, org_id: str, repo_name: str, variable_name: str, variable: dict[str, Any]) -> None:
        if len(variable) > 0:
            self.rest_api.repo.update_variable(org_id, repo_name, variable_name, variable)

    def add_repo_variable(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        self.rest_api.repo.add_variable(org_id, repo_name, data)

    def delete_repo_variable(self, org_id: str, repo_name: str, variable_name: str) -> None:
        self.rest_api.repo.delete_variable(org_id, repo_name, variable_name)

    def dispatch_workflow(self, org_id: str, repo_name: str, workflow_name: str) -> bool:
        return self.rest_api.repo.dispatch_workflow(org_id, repo_name, workflow_name)

    def get_repo_ids(self, org_id: str, repo_names: list[str]) -> list[str]:
        repo_ids = []
        for repo_name in repo_names:
            repo_data = self.get_repo_data(org_id, repo_name)
            repo_ids.append(repo_data["id"])
        return repo_ids

    def get_actor_node_ids(self, actor_names: list[str]) -> list[str]:
        return list(map(lambda x: x[1][1], self.get_actor_ids_with_type(actor_names)))

    def get_actor_ids_with_type(self, actor_names: list[str]) -> list[tuple[str, tuple[int, str]]]:
        result = []
        for actor in actor_names:
            if actor.startswith("@"):
                # if it starts with a @, it's either a user or team:
                #    - team-names contains a / in its slug
                #    - user-names are not allowed to contain a /
                if "/" in actor:
                    try:
                        result.append(("Team", self.rest_api.org.get_team_ids(actor[1:])))
                    except RuntimeError:
                        utils.print_warn(f"team '{actor[1:]}' does not exist, skipping")
                else:
                    try:
                        result.append(("User", self.rest_api.user.get_user_ids(actor[1:])))
                    except RuntimeError:
                        utils.print_warn(f"user '{actor[1:]}' does not exist, skipping")
            else:
                # it's an app
                try:
                    result.append(("App", self.rest_api.app.get_app_ids(actor)))
                except RuntimeError:
                    utils.print_warn(f"app '{actor}' does not exist, skipping")

        return result

    def get_app_node_ids(self, app_names: set[str]) -> dict[str, str]:
        return {app_name: self.rest_api.app.get_app_ids(app_name)[1] for app_name in app_names}

    def get_app_ids(self, app_names: set[str]) -> dict[str, str]:
        return {app_name: self.rest_api.app.get_app_ids(app_name)[0] for app_name in app_names}

    def get_ref_for_pull_request(self, org_id: str, repo_name: str, pull_number: str) -> str:
        return self.rest_api.repo.get_ref_for_pull_request(org_id, repo_name, pull_number)

    def open_browser_with_logged_in_user(self, org_id: str) -> None:
        self.web_client.open_browser_with_logged_in_user(org_id)
