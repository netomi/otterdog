#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import dataclasses
import time
from abc import abstractmethod
from typing import Optional, Protocol

import mintotp  # type: ignore

from otterdog import utils


@dataclasses.dataclass
class Credentials:
    """
    A simple data class to hold credential information to access GitHub.
    """

    _username: Optional[str]
    _password: Optional[str]
    _totp_secret: Optional[str]
    _github_token: Optional[str]

    _last_totp: Optional[str] = None

    @property
    def username(self) -> str:
        if self._username is None:
            raise RuntimeError("username not available")
        else:
            return self._username

    @property
    def password(self) -> str:
        if self._password is None:
            raise RuntimeError("password not available")
        else:
            return self._password

    @property
    def totp(self) -> str:
        if self._totp_secret is None:
            raise RuntimeError("totp_secret not available")

        while True:
            totp = mintotp.totp(self._totp_secret)
            utils.print_trace(f"generated totp '{totp}'")

            if self._last_totp is None or totp != self._last_totp:
                self._last_totp = totp
                return totp
            else:
                utils.print_info("waiting 3s till generating new totp ...")
                time.sleep(3)

    @property
    def github_token(self) -> str:
        if self._github_token is None:
            raise RuntimeError("github_token not available")
        else:
            return self._github_token

    def __str__(self) -> str:
        return "Credentials(username={})".format(self.username)


class CredentialProvider(Protocol):
    @abstractmethod
    def get_credentials(
        self, eclipse_project: Optional[str], data: dict[str, str], only_token: bool = False
    ) -> Credentials:
        ...

    @abstractmethod
    def get_secret(self, data: str) -> str:
        ...
