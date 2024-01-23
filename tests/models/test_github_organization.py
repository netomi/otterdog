#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
import unittest

from otterdog.config import OtterdogConfig
from otterdog.models.github_organization import GitHubOrganization


class GitHubOrganizationTest(unittest.TestCase):
    TEST_ORG = "test-org"
    BASE_TEMPLATE_URL = "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main"

    def setUp(self):
        base_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources")
        otterdog_config_file = os.path.join(base_dir, "otterdog.json")

        self.otterdog_config = OtterdogConfig(otterdog_config_file, True)
        self.org_config = self.otterdog_config.get_organization_config(self.TEST_ORG)
        self.jsonnet_config = self.org_config.jsonnet_config
        self.jsonnet_config.init_template()

    def test_load_from_file(self):
        organization = GitHubOrganization.load_from_file(
            self.TEST_ORG, self.jsonnet_config.org_config_file, self.otterdog_config
        )

        assert organization.github_id == "test-org"
        assert len(organization.webhooks) == 1
        assert len(organization.repositories) == 2
