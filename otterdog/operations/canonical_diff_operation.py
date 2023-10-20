# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Style, Fore

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import sort_jsonnet, strip_trailing_commas

from . import Operation


class CanonicalDiffOperation(Operation):
    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        self.printer.println(f"Showing diff to a canonical version of the configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")

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

        with open(org_file_name, "r") as file:
            original_config = file.read()

        original_config_without_comments: list[str] = strip_trailing_commas(
            sort_jsonnet(list(filter(lambda x: not x.strip().startswith("#"), original_config.split("\n"))))
        )

        canonical_config = organization.to_jsonnet(jsonnet_config)
        canonical_config_as_lines = strip_trailing_commas(sort_jsonnet(canonical_config.split("\n")))

        for line in self._diff(original_config_without_comments, canonical_config_as_lines, "original", "canonical"):
            if line.startswith("+"):
                self.printer.println(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
            elif line.startswith("-"):
                self.printer.println(f"{Fore.RED}{line}{Style.RESET_ALL}")
            else:
                self.printer.println(line)

        return 0

    @staticmethod
    def _diff(a, b, name_a, name_b):
        from tempfile import NamedTemporaryFile
        from subprocess import Popen, PIPE

        with NamedTemporaryFile() as file:
            file.write(bytes("\n".join(a), "utf-8"))
            file.flush()
            p = Popen(
                ['diff', '--label', name_a, '--label', name_b, '-u', '-w', '-', file.name], stdin=PIPE, stdout=PIPE
            )
            out, err = p.communicate(bytes("\n".join(b), "utf-8"))

            for line in out.decode("utf-8").split("\n"):
                yield line
