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
from typing import Any, TypeVar, Optional

from jsonbender import bend, S, OptionalS  # type: ignore

from otterdog.models import ModelObject, ValidationContext, LivePatchContext, LivePatchHandler
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, is_unset, associate_by_key

RS = TypeVar("RS", bound="Ruleset")


@dataclasses.dataclass
class Ruleset(ModelObject, abc.ABC):
    """
    Represents a Ruleset.
    """

    id: str = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    node_id: str = dataclasses.field(metadata={"external_only": True})
    enforcement: str

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        pass

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

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

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: Optional[ModelObject],
        current_object: Optional[ModelObject],
        parent_object: Optional[ModelObject],
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        pass

    @classmethod
    def generate_live_patch_of_list(
        cls,
        expected_rulesets: list[RS],
        current_rulesets: list[RS],
        parent_object: Optional[ModelObject],
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        expected_rulesets_by_name = associate_by_key(expected_rulesets, lambda x: x.name)

        for current_secret in current_rulesets:
            secret_name = current_secret.name

            expected_secret = expected_rulesets_by_name.get(secret_name)
            if expected_secret is None:
                cls.generate_live_patch(None, current_secret, parent_object, context, handler)
                continue

            # pop the already handled secret
            expected_rulesets_by_name.pop(expected_secret.name)

            cls.generate_live_patch(expected_secret, current_secret, parent_object, context, handler)

        for secret_name, secret in expected_rulesets_by_name.items():
            cls.generate_live_patch(secret, None, parent_object, context, handler)
