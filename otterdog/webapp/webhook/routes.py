# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Any

from flask import request, Response

from logging import getLogger

from otterdog.webapp.tasks.pull_request_event import handle_pull_request_event

from . import blueprint

logger = getLogger(__name__)


# receive webhook events from GitHub
@blueprint.route("/receive", methods=['POST'])
def receive():
    logger.debug("received request: %s", request)

    json_data = request.get_json()

    if is_pull_request_event(json_data):
        handle_pull_request_event.delay(json_data)
    else:
        logger.debug(f"received unknown event, skipping:\n{json.dumps(json_data, indent=2)}")

    return Response({}, mimetype="application/json", status=200)


def is_pull_request_event(json_data: dict[str, Any]) -> bool:
    return "pull_request" in json_data


def is_push_event(json_data: dict[str, Any]) -> bool:
    for attr in ["ref", "before", "after"]:
        if attr not in json_data:
            return False

    return True
