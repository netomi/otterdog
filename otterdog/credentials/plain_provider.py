# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Optional

from otterdog.credentials import Credentials, CredentialProvider


class PlainProvider(CredentialProvider):
    """
    A simple credential provider for storing tokens in memory.
    """

    KEY_API_TOKEN = "api_token"

    def get_credentials(self, eclipse_project: Optional[str], data: dict[str, str]) -> Credentials:
        github_token = data[self.KEY_API_TOKEN]
        return Credentials("", "", github_token, "")

    def get_secret(self, key_data: str) -> str:
        raise RuntimeError("plain provider does not support secrets")

    def __str__(self):
        return "PlainProvider()"
