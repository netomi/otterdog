# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Style

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import is_set_and_present

from . import Operation


class SyncTemplateOperation(Operation):
    def __init__(self, repo: str):
        super().__init__()
        self._repo = repo

    def pre_execute(self) -> None:
        self.printer.println(f"Syncing template repos for configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file

            if not os.path.exists(org_file_name):
                self.printer.print_error(
                    f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first"
                )
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name, self.config)
            except RuntimeError as ex:
                self.printer.print_error(f"failed to load configuration: {str(ex)}")
                return 1

            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with GitHubProvider(credentials) as provider:
                rest_api = provider.rest_api

                for repo in organization.repositories:
                    if repo.archived is True:
                        continue

                    if repo.name != self._repo:
                        continue

                    if is_set_and_present(repo.template_repository):
                        self.printer.println(f'Syncing {Style.BRIGHT}repository["{repo.name}"]{Style.RESET_ALL}')
                        updated_files = rest_api.repo.sync_from_template_repository(
                            github_id,
                            repo.name,
                            repo.template_repository,
                            repo.post_process_template_content,
                        )

                        self.printer.level_up()
                        for file in updated_files:
                            self.printer.println(f"updated file '{file}'")
                        self.printer.level_down()

            return 0

        finally:
            self.printer.level_down()
