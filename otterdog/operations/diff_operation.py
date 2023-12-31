# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from abc import abstractmethod
from typing import Any, Optional

from otterdog.config import OtterdogConfig, OrganizationConfig
from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject, LivePatch, LivePatchType, LivePatchContext
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import IndentingPrinter, print_warn, print_error, Change, is_info_enabled, style

from . import Operation
from .validate import ValidateOperation


class DiffStatus:
    def __init__(self):
        self.additions = 0
        self.differences = 0
        self.deletions = 0

    def total_changes(self, include_deletions: bool) -> int:
        if include_deletions:
            return self.additions + self.differences + self.deletions
        else:
            return self.additions + self.differences


class DiffOperation(Operation):
    def __init__(self, no_web_ui: bool, update_webhooks: bool, update_secrets: bool, update_filter: str):
        super().__init__()

        self.no_web_ui = no_web_ui
        self.update_webhooks = update_webhooks
        self.update_secrets = update_secrets
        self.update_filter = update_filter
        self._gh_client: Optional[GitHubProvider] = None
        self._validator = ValidateOperation()
        self._template_dir: Optional[str] = None
        self._org_config: Optional[OrganizationConfig] = None

    @property
    def template_dir(self) -> str:
        assert self._template_dir is not None
        return self._template_dir

    @property
    def org_config(self) -> OrganizationConfig:
        assert self._org_config is not None
        return self._org_config

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)
        self._validator.init(config, printer)

    def execute(self, org_config: OrganizationConfig) -> int:
        self._org_config = org_config

        self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={org_config.github_id}]")

        try:
            self._gh_client = self.setup_github_client(org_config)
        except RuntimeError as e:
            print_error(f"invalid credentials\n{str(e)}")
            return 1

        self.printer.level_up()

        try:
            return self._generate_diff(org_config)
        finally:
            self.printer.level_down()
            self._gh_client.close()

    def setup_github_client(self, org_config: OrganizationConfig) -> GitHubProvider:
        return GitHubProvider(self.config.get_credentials(org_config))

    @property
    def gh_client(self) -> GitHubProvider:
        assert self._gh_client is not None
        return self._gh_client

    def verbose_output(self):
        return True

    def resolve_secrets(self) -> bool:
        return True

    def _generate_diff(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()
        self._template_dir = jsonnet_config.template_dir

        org_file_name = jsonnet_config.org_config_file

        if not os.path.exists(org_file_name):
            print_error(f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first")
            return 1

        try:
            expected_org = self.load_expected_org(github_id, org_file_name)
        except RuntimeError as e:
            print_error(f"failed to load configuration\n{str(e)}")
            return 1

        # We validate the configuration first and only calculate a plan if
        # there are no validation errors.
        (
            validation_infos,
            validation_warnings,
            validation_errors,
        ) = self._validator.validate(expected_org, jsonnet_config.template_dir)
        if validation_errors > 0:
            self.printer.println("Planning aborted due to validation errors.")
            return validation_errors

        if validation_infos > 0 and not is_info_enabled():
            self.printer.println(
                f"there have been {validation_infos} validation infos, "
                f"enable verbose output with '-v' to to display them."
            )

        try:
            current_org = self.load_current_org(github_id, jsonnet_config)
        except RuntimeError as e:
            print_error(f"failed to load current configuration\n{str(e)}")
            return 1

        diff_status = DiffStatus()
        live_patches = []

        def handle(patch: LivePatch) -> None:
            live_patches.append(patch)

            match patch.patch_type:
                case LivePatchType.ADD:
                    assert patch.expected_object is not None
                    self.handle_add_object(github_id, patch.expected_object, patch.parent_object)
                    diff_status.additions += 1

                case LivePatchType.REMOVE:
                    assert patch.current_object is not None
                    self.handle_delete_object(github_id, patch.current_object, patch.parent_object)
                    diff_status.deletions += 1

                case LivePatchType.CHANGE:
                    assert patch.changes is not None
                    assert patch.current_object is not None
                    assert patch.expected_object is not None

                    diff_status.differences += self.handle_modified_object(
                        github_id,
                        patch.changes,
                        False,
                        patch.current_object,
                        patch.expected_object,
                        patch.parent_object,
                    )

        context = LivePatchContext(
            github_id, self.update_webhooks, self.update_secrets, self.update_filter, expected_org.settings
        )
        expected_org.generate_live_patch(current_org, context, handle)

        # add a warning that otterdog potentially must be run a second time
        # to fully apply all setting.
        if "web_commit_signoff_required" in context.modified_org_settings:
            change = context.modified_org_settings["web_commit_signoff_required"]
            if change.to_value is False:
                if self.verbose_output():
                    print_warn(
                        "Setting 'web_commit_signoff_required' setting has been disabled on "
                        "organization level. \nThe effective setting on repo level can only be "
                        "determined once this change has been applied.\n"
                        "You need to run otterdog another time to fully ensure "
                        "that the correct configuration is applied."
                    )

        # resolve secrets for collected patches
        if self.resolve_secrets():
            for live_patch in live_patches:
                if live_patch.expected_object is not None:
                    live_patch.expected_object.resolve_secrets(self.config.get_secret)

        self.handle_finish(github_id, diff_status, live_patches)
        return 0

    def load_expected_org(self, github_id: str, org_file_name: str) -> GitHubOrganization:
        return GitHubOrganization.load_from_file(github_id, org_file_name, self.config)

    def load_current_org(self, github_id: str, jsonnet_config: JsonnetConfig) -> GitHubOrganization:
        return GitHubOrganization.load_from_provider(
            github_id, jsonnet_config, self.gh_client, self.no_web_ui, self.printer
        )

    @abstractmethod
    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        ...

    @abstractmethod
    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        ...

    @abstractmethod
    def handle_modified_object(
        self,
        org_id: str,
        modified_object: dict[str, Change[Any]],
        forced_update: bool,
        current_object: ModelObject,
        expected_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> int:
        ...

    @abstractmethod
    def handle_finish(self, org_id: str, diff_status: DiffStatus, patches: list[LivePatch]) -> None:
        ...
