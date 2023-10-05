#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import os.path
import re
from io import StringIO
from typing import Optional, Any
from flask import current_app

from celery import shared_task  # type: ignore

from .json.models import PullRequestEvent
from ...providers.github import RestApi
from ...providers.github.rest.auth.app import AppAuthStrategy
from ...providers.github.rest.auth.token import TokenAuthStrategy

from ...config import JsonnetConfig, OrganizationConfig, OtterdogConfig
from ...operations.local_plan_operation import LocalPlanOperation
from ...utils import IndentingPrinter


@shared_task
def handle_pull_request(json_data: dict[str, Any]) -> None:
    event = PullRequestEvent.model_validate(json_data)

    rest_api = RestApi(
        AppAuthStrategy(current_app.config["GITHUB_APP_ID"], current_app.config["GITHUB_APP_PRIVATE_KEY"])
    )

    token = rest_api.app.create_installation_access_token(str(event.installation.id))
    org_client = RestApi(TokenAuthStrategy(token))

    org_id = event.organization.login

    jsonnet_config = JsonnetConfig(
        org_id, "app_orgs", "https://github.com/EclipseFdn/otterdog-defaults#otterdog-defaults.libsonnet@main", False
    )

    credential_data = {"provider": "plain", "api_token": token}

    otterdog_config = OtterdogConfig("otterdog-test.json", False)

    org_config = OrganizationConfig(org_id, org_id, None, ".eclipsefdn", jsonnet_config, credential_data)

    if not os.path.exists(jsonnet_config.org_dir):
        os.makedirs(jsonnet_config.org_dir)

    jsonnet_config.init_template()

    # get HEAD
    path = f"otterdog/{org_id}.jsonnet"

    content = get_content(
        org_client,
        org_id,
        ".eclipsefdn",
        path,
    )

    org_file_name = jsonnet_config.org_config_file + "-HEAD"
    with open(org_file_name, "w") as file:
        file.write(content)

    # get from PR
    content = get_content(org_client, org_id, ".eclipsefdn", path, str(event.pull_request.number))

    org_file_name = jsonnet_config.org_config_file
    with open(org_file_name, "w") as file:
        file.write(content)

    output = StringIO()
    printer = IndentingPrinter(output)
    operation = LocalPlanOperation("-HEAD", False, False, "")
    operation.init(otterdog_config, printer)

    operation.execute(org_config)

    text = output.getvalue()
    print(text)

    result = f"""
<details>
<summary>Diff for {event.pull_request.head.sha}</summary>

```diff
{escape_for_github(text)}
```

</details>
    """
    org_client.issue.create_comment(org_id, ".eclipsefdn", str(event.pull_request.number), result)


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
