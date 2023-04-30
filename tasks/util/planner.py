from json import loads as json_loads
from json.decoder import JSONDecodeError
from requests import post
from time import sleep

# The conversion here must match the enum in the HttpMessage definition in
# the planner protobuf file (faabric/src/planner/planner.proto)
PLANNER_HTTP_MESSAGE_TYPE = {
    "RESET": 1,
    "GET_APP_MESSAGES": 2,
    "GET_AVAILABLE_HOSTS": 3,
    "GET_CONFIG": 4,
    "FLUSH_AVAILABLE_HOSTS": 5,
    "FLUSH_EXECUTORS": 6,
    "EXECUTE": 7,
    "EXECUTE_STATUS": 8,
}

# ----------
# Util
# ----------


def prepare_planner_msg(msg_type, msg_body=None):
    if msg_type not in PLANNER_HTTP_MESSAGE_TYPE:
        print(
            "Unrecognised HTTP message type for planner: {}".format(msg_type)
        )
        raise RuntimeError("Unrecognised planner HTTP message type")

    planner_msg = {
        "http_type": PLANNER_HTTP_MESSAGE_TYPE[msg_type],
    }

    if msg_body:
        # FIXME: currently we use protobuf for JSON (de)-serialisation in
        # faabric. In addition, we nest a JSON as a string in another JSON,
        # which means that boolean values (in JSON) are serialised in the
        # nested string as True, False. Unfortunately, protobuf only identifies
        # as booleans the string literals `true` and `false` (with lower-case).
        # So we need to be careful here
        boolean_flags_in_nested_msg = ["mpi", "sgx"]
        for key in boolean_flags_in_nested_msg:
            if key in msg_body:
                msg_body[key] = str(msg_body[key]).lower()

        planner_msg["payload"] = str(msg_body)

    return planner_msg


# ----------
# RESET
# ----------


def reset(host, port):
    """
    Reset the planner with an HTTP request. Reset clears the available hosts,
    and the scheduling state
    """
    url = "http://{}:{}".format(host, port)

    planner_msg = prepare_planner_msg("RESET")

    response = post(url, json=planner_msg, timeout=None)

    if response.status_code != 200:
        print(
            "Error resetting planner (code: {}): {}".format(
                response.status_code, response.text
            )
        )
        raise RuntimeError("Error resetting planner")


def get_registered_workers(host, port):
    """
    Get the set of workers registered with the planner
    """
    url = "http://{}:{}".format(host, port)
    planner_msg = prepare_planner_msg("GET_AVAILABLE_HOSTS")

    response = post(url, json=planner_msg, timeout=None)

    if response.status_code != 200:
        print(
            "Error waiting for workers (code: {}): {}".format(
                response.status_code, response.text
            )
        )
        raise RuntimeError("Error waiting for workers")

    try:
        response_json = json_loads(response.text)
    except JSONDecodeError as e:
        print("Error deserialising JSON message: {}".format(e.msg))
        print("Actual message: {}".format(response.text))

    if "hosts" not in response_json:
        return None

    return response_json["hosts"]


def get_app_messages(host, port, app_id):
    """
    Get all the messages recorded for an app
    """
    url = "http://{}:{}".format(host, port)
    # Currently we only need to set the app id to get the app messages
    msg = {
        "appId": app_id,
    }
    planner_msg = prepare_planner_msg("GET_APP_MESSAGES", msg)

    response = post(url, json=planner_msg, timeout=None)
    if response.status_code != 200:
        print(
            "Error getting app messages for app {} (code: {}): {}".format(
                app_id, response.status_code, response.text
            )
        )
        raise RuntimeError("Error posting GET_APP_MESSAGES")

    try:
        response_json = json_loads(response.text)
    except JSONDecodeError as e:
        print("Error deserialising JSON message: {}".format(e.msg))
        print("Actual message: {}".format(response.text))

    if "messages" not in response_json:
        return []

    return response_json["messages"]


def get_msg_result(host, port, msg):
    """
    Wait for a message result to be registered with the planner
    """
    url = "http://{}:{}".format(host, port)
    planner_status_msg = prepare_planner_msg("EXECUTE_STATUS", msg)
    status_response = post(url, json=planner_status_msg)

    while (
        status_response.status_code != 200
        or status_response.text.startswith("RUNNING")
    ):
        if not status_response.text:
            print(
                "Empty response text (status: {})".format(
                    status_response.status
                )
            )
            raise RuntimeError("Empty status response")
        elif (
            status_response.status_code >= 400
            or status_response.text.startswith("FAILED")
        ):
            print("Error running task: {}".format(status_response.status))
            print("Error message: {}".format(status_response.text))
            raise RuntimeError("Error running task!")

        sleep(2)
        status_response = post(url, json=planner_status_msg)

    try:
        result_json = json_loads(status_response.text)
    except JSONDecodeError as e:
        print("Error deserialising JSON message: {}".format(e.msg))
        print("Actual message: {}".format(status_response.text))

    return result_json


def get_app_result(host, port, app_id, app_size):
    """
    Wait for all messages in an app identified by `app_id` to have finished.
    We will wait for a total of `app_size` messages
    """
    # First, poll the planner until all messages are registered with the app
    registered_msgs = get_app_messages(host, port, app_id)
    while len(registered_msgs) != app_size:
        print(
            "Waiting for messages to be registered with app {} ({}/{})".format(
                app_id, len(registered_msgs), app_size
            )
        )
        sleep(2)
        registered_msgs = get_app_messages(host, port, app_id)

    print(
        "All messages registerd with app {} ({}/{})".format(
            app_id, len(registered_msgs), app_size
        )
    )
    # Now, for each message, wait for it to be completed
    results = []
    for i, msg in enumerate(registered_msgs):
        print(
            "Polling message {} (app: {}, {}/{})".format(
                msg["id"], app_id, i + 1, len(registered_msgs)
            )
        )
        result_json = get_msg_result(host, port, msg)
        results.append(result_json)

    return results


def print_planner_resources(host, port):
    """
    Helper method to visualise the state of the planner
    """

    def print_line(host_msg):
        line = "{}\t".format(host_msg["ip"])
        used_slots = host_msg["usedSlots"] if "usedSlots" in host_msg else 0
        for i in range(host_msg["slots"]):
            if i < used_slots:
                line += " [X]"
            else:
                line += " [ ]"
        print(line)

    header = "-------------- PLANNER RESOURCES ---------------"
    footer = "------------------------------------------------"

    registered_workers = get_registered_workers(host, port)
    print(header)
    for worker in registered_workers:
        print_line(worker)
    print(footer)
