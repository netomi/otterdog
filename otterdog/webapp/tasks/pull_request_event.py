# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from logging import getLogger
from typing import Any

from celery import shared_task  # type: ignore
from pydantic import ValidationError

from .models import PullRequestEvent
from .operations.apply import apply_pull_request
from .operations.validate import validate_pull_request

logger = getLogger(__name__)


@shared_task
def handle_pull_request_event(event_data: dict[str, Any]) -> None:
    try:
        event = PullRequestEvent.model_validate(event_data)
    except ValidationError:
        logger.error("failed to load pull request event data", exc_info=True)
        return

    if event.action in ["opened", "synchronize", "edited"] and event.pull_request.draft is False:
        validate_pull_request(event)
    elif event.action in ["closed"] and event.pull_request.merged is True:
        apply_pull_request(event)
