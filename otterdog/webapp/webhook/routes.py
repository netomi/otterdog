# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json

from flask import request, Response

from logging import getLogger

from otterdog.webapp.tasks.pull_requests import handle_pull_request

from . import blueprint

logger = getLogger(__name__)


# receive webhook events from GitHub
@blueprint.route("/receive", methods=['POST'])
def receive():
    logger.debug("received request: %s", request)

    json_data = request.get_json()

    if "pull_request" in json_data:
        handle_pull_request.delay(json_data)
    else:
        logger.debug(f"received unknown event, skipping:\n{json.dumps(json_data, indent=2)}")

    return Response({}, mimetype="application/json", status=200)
