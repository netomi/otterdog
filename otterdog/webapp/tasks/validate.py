# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
import re

from io import StringIO
from logging import getLogger
from typing import Optional

from otterdog.config import OtterdogConfig
from otterdog.operations.local_plan_operation import LocalPlanOperation
from otterdog.providers.github import RestApi
from otterdog.utils import IndentingPrinter

from . import get_rest_api_for_installation
from .models import PullRequestEvent

logger = getLogger(__name__)


def validate_pull_request(event: PullRequestEvent) -> None:
    """Validates a PR and adds the result as a comment."""

    # TODO: make the config configurable and load it, e.g. from github
    otterdog_config = OtterdogConfig("otterdog-test.json", False)

    if event.repository.name != otterdog_config.default_config_repo:
        return

    logger.info("validating pull request #%d for repo '%s'", event.pull_request.number, event.repository.full_name)

    org_id = event.organization.login
    pull_request_number = str(event.pull_request.number)

    rest_api = get_rest_api_for_installation(event.installation.id)

    org_config = otterdog_config.get_organization_config(org_id)
    org_config.credential_data = {"provider": "plain", "api_token": rest_api.token}
    jsonnet_config = org_config.jsonnet_config

    if not os.path.exists(jsonnet_config.org_dir):
        os.makedirs(jsonnet_config.org_dir)

    jsonnet_config.init_template()

    # get BASE config
    get_config(rest_api, org_id, otterdog_config.default_config_repo, jsonnet_config.org_config_file + "-BASE")

    # get HEAD config from PR
    get_config(
        rest_api,
        org_id,
        otterdog_config.default_config_repo,
        jsonnet_config.org_config_file,
        pull_request_number,
    )

    output = StringIO()
    printer = IndentingPrinter(output)
    operation = LocalPlanOperation("-BASE", False, False, "")
    operation.init(otterdog_config, printer)

    operation.execute(org_config)

    text = output.getvalue()
    logger.info(text)

    result = f"""
<details>
<summary>Diff for {event.pull_request.head.sha}</summary>

```diff
{escape_for_github(text)}
```

</details>
    """

    rest_api.issue.create_comment(org_id, otterdog_config.default_config_repo, pull_request_number, result)


def get_config(rest_api: RestApi, org_id: str, repo: str, filename: str, pull_request: Optional[str] = None):
    path = f"otterdog/{org_id}.jsonnet"
    content = get_content(rest_api, org_id, repo, path, pull_request)
    with open(filename, "w") as file:
        file.write(content)


def get_content(client: RestApi, org_id: str, repo: str, path: str, pull_request: Optional[str] = None) -> str:
    if pull_request is not None:
        ref = client.repo.get_ref_for_pull_request(org_id, repo, pull_request)
    else:
        ref = None

    content = client.content.get_content(
        org_id,
        repo,
        path,
        ref,
    )

    return content


def escape_for_github(text: str) -> str:
    lines = text.splitlines()

    output = []
    for line in lines:
        ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
        line = ansi_escape.sub('', line)

        diff_escape = re.compile(r'(\s+)([-+!])')
        line = diff_escape.sub(r'\g<2>\g<1>', line)

        diff_escape2 = re.compile(r'(\s+)(~)')
        line = diff_escape2.sub(r'!\g<1>', line)

        output.append(line)

    return "\n".join(output)
