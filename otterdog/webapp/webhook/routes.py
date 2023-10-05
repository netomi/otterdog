import json

from flask import request, Response

from . import blueprint

from .tasks import handle_pull_request


# receive webhook events from GitHub
@blueprint.route("/receive", methods=['POST'])
def receive():
    print(request)

    json_data = request.get_json()

    print(json.dumps(json_data, indent=2))

    if "pull_request" in json_data:
        handle_pull_request.delay(json_data)
    else:
        print("unknown event")

    return Response({}, mimetype="application/json", status=200)
