#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from datetime import datetime
from typing import Any

from otterdog.utils import print_debug

from . import RestApi, RestClient, parse_date_string
from ..exception import GitHubException


class AppClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    def get_authenticated_app(self) -> dict[str, Any]:
        print_debug("retrieving authenticated app")

        try:
            return self.requester.request_json("GET", "/app")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving authenticated app:\n{ex}").with_traceback(tb)

    def get_app_installations(self) -> list[dict[str, Any]]:
        print_debug("retrieving app installations")

        try:
            return self.requester.request_paged_json("GET", "/app/installations")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving authenticated app:\n{ex}").with_traceback(tb)

    def create_installation_access_token(self, installation_id: str) -> tuple[str, datetime]:
        print_debug(f"creating an installation access token for installation '{installation_id}'")

        try:
            response = self.requester.request_json("POST", f"/app/installations/{installation_id}/access_tokens")
            return response["token"], parse_date_string(response["expires_at"])
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed creating installation access token:\n{ex}").with_traceback(tb)

    def get_app_ids(self, app_slug: str) -> tuple[int, str]:
        print_debug("retrieving app node id")

        try:
            response = self.requester.request_json("GET", f"/apps/{app_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving app node id:\n{ex}").with_traceback(tb)
