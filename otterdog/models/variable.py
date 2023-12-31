# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
from typing import Any, TypeVar

from jsonbender import bend, S, OptionalS  # type: ignore

from otterdog.models import ModelObject, ValidationContext, FailureType
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, is_unset

VT = TypeVar("VT", bound="Variable")


@dataclasses.dataclass
class Variable(ModelObject, abc.ABC):
    """
    Represents a Variable.
    """

    name: str = dataclasses.field(metadata={"key": True})
    value: str

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if self.name.startswith("GITHUB_"):
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} starts with prefix 'GITHUB_' which is not allowed for variables.",
            )

    @classmethod
    def from_model_data(cls, data: dict[str, Any]):
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]):
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return mapping

    @classmethod
    def get_mapping_to_provider(cls, org_id: str, data: dict[str, Any], provider: GitHubProvider) -> dict[str, Any]:
        return {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }
