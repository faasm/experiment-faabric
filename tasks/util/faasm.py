from configparser import ConfigParser
from json import loads as json_loads

# TODO(planner):
# from json.decoder import JSONDecodeError
from os import environ
from os.path import expanduser, join, exists
from pprint import pprint
from requests import post
from tasks.util.planner import (
    # TODO(planner):
    # get_app_result,
    get_registered_workers as get_planner_registerd_workers,
    # prepare_planner_msg,
    reset as do_reset_planner,
)
from time import sleep


if "FAASM_INI_FILE" in environ:
    FAASM_INI_FILE = environ["FAASM_INI_FILE"]
else:
    FAASM_INI_FILE = join(expanduser("~"), ".config", "faasm.ini")


def get_faasm_ini_value(section, key):
    if not exists(FAASM_INI_FILE):
        print("Expected to find faasm config at {}".format(FAASM_INI_FILE))
        raise RuntimeError("Did not find faasm config")

    config = ConfigParser()
    config.read(FAASM_INI_FILE)
    return config[section].get(key, "")


def get_faasm_upload_host_port():
    host = get_faasm_ini_value("Faasm", "upload_host")
    port = get_faasm_ini_value("Faasm", "upload_port")

    print("Using faasm upload {}:{}".format(host, port))
    return host, port


def get_faasm_invoke_host_port():
    host = get_faasm_ini_value("Faasm", "invoke_host")
    port = get_faasm_ini_value("Faasm", "invoke_port")

    print("Using faasm invoke {}:{}".format(host, port))
    return host, port


def get_faasm_planner_host_port():
    host = get_faasm_ini_value("Faasm", "planner_host")
    port = get_faasm_ini_value("Faasm", "planner_port")
    return host, port


def get_faasm_worker_ips():
    ips = get_faasm_ini_value("Faasm", "worker_ips")
    ips = [p.strip() for p in ips.split(",") if p.strip()]

    print("Using faasm worker IPs: {}".format(ips))
    return ips


def get_faasm_worker_pods():
    pods = get_faasm_ini_value("Faasm", "worker_names")
    pods = [p.strip() for p in pods.split(",") if p.strip()]

    print("Using faasm worker pods: {}".format(pods))
    return pods


def get_faasm_exec_time_from_json(result_json):
    """
    Return the execution time (included in Faasm's response JSON) in seconds
    """
    actual_time = (
        # TODO(planner)
        # float(int(result_json["finish_ts"]) - int(result_json["start_ts"]))
        float(int(result_json["finish"]) - int(result_json["timestamp"]))
        / 1000
    )

    return actual_time


def flush_workers():
    """
    Flush faasm workers through the planner
    """
    # Prepare URL and headers
    # TODO(planner):
    #     host, port = get_faasm_planner_host_port()
    #     url = "http://{}:{}".format(host, port)
    #     msg = prepare_planner_msg("FLUSH_EXECUTORS")
    #     response = post(url, json=msg, timeout=None)
    #     if response.status_code != 200:
    #         print(
    #             "Flush request failed: {}:\n{}".format(
    #                 response.status_code, response.text
    #             )
    #         )
    # Prepare URL and headers
    host, port = get_faasm_invoke_host_port()
    url = "http://{}:{}".format(host, port)

    # Prepare message
    msg = {"type": 3}
    # print("Flushing functions, state, and shared files from workers")
    # print("Posting to {} msg:".format(url))
    # pprint(msg)
    response = post(url, json=msg, timeout=None)
    if response.status_code != 200:
        print(
            "Flush request failed: {}:\n{}".format(
                response.status_code, response.text
            )
        )
    print("Waiting for flush to propagate...")
    sleep(5)
    print("Done waiting")


# TODO(planner)
# def post_async_msg_and_get_result_json(msg, url, verbose=False):
#     if verbose:
#         print("Posting to {} msg:".format(url))
#         pprint(msg)
#
#     planner_msg_execute = prepare_planner_msg("EXECUTE", msg)
#
#     # Post asynch request
#     response = post(url, json=planner_msg_execute, timeout=None)
#     if response.status_code != 200:
#         print(
#             "Initial request failed: {}:\n{}".format(
#                 response.status_code, response.text
#             )
#         )
#         raise RuntimeError("Error sending EXECUTE request to planner")
#
#     try:
#         execute_msg = json_loads(response.text)
#     except JSONDecodeError as e:
#         print("Error deserialising JSON message: {}".format(e.msg))
#         print("Actual message: {}".format(response.text))
#         raise RuntimeError("Error deserialising EXECUTE response")
#
#     app_id = execute_msg["appId"]
#     # TODO: this may have to be re-considered for OpenMP calls
#     app_size = (
#   execute_msg["mpi_world_size"] if "mpi_world_size" in execute_msg else 1
#     )
#
#     # Get app results
#     host, port = get_faasm_planner_host_port()
#     # We return the JSON for the first message only, for backwards
#     # compatibility. We can consider changing this eventually
#     return get_app_result(host, port, app_id, app_size)[0]
def post_async_msg_and_get_result_json(msg, url):
    print("Posting to {} msg:".format(url))
    pprint(msg)

    # Post asynch request
    response = post(url, json=msg, timeout=None)
    # Get the async message id
    if response.status_code != 200:
        print(
            "Initial request failed: {}:\n{}".format(
                response.status_code, response.text
            )
        )
    print("Response: {}".format(response.text))
    msg_id = int(response.text.strip())

    # Start polling for the result
    print("Polling message {}".format(msg_id))
    while True:
        interval = 2
        sleep(interval)

        status_msg = {
            "user": msg["user"],
            "function": msg["function"],
            "status": True,
            "id": msg_id,
        }
        response = post(url, json=status_msg)

        if not response.text or response.text.startswith("FAILED"):
            raise RuntimeError("Error running task!")
        elif response.text.startswith("RUNNING"):
            continue
        elif not response.text:
            raise RuntimeError("Empty status response")

        # If we reach this point it means the call has succeeded
        result_json = json_loads(response.text, strict=False)
        # print(result_json)
        return result_json


def wait_for_workers(expected_num_workers):
    """
    Wait for the workers to have reigstered with the planner
    """
    host, port = get_faasm_planner_host_port()

    def get_num_registered_workers():
        registred_workers = get_planner_registerd_workers(host, port)
        return len(registred_workers) if registred_workers else 0

    num_registered = get_num_registered_workers()
    while num_registered != expected_num_workers:
        print(
            "The # of workers registered with the planner differs from the"
            " expected number ({} != {})".format(
                num_registered, expected_num_workers
            )
        )
        sleep(2)
        num_registered = get_num_registered_workers()

    print("The # of workers registered with the planner is the expected one!")


def reset_planner():
    """
    Reset the planner
    """
    host, port = get_faasm_planner_host_port()
    do_reset_planner(host, port)
