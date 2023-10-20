# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from colorama import Style

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider

from . import Operation


class WebLoginOperation(Operation):
    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        pass

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.println(f"\nOrganization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")

        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with GitHubProvider(credentials) as provider:
                provider.open_browser_with_logged_in_user(github_id)

            return 0
        finally:
            self.printer.level_down()
