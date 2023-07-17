from faasmctl.util.config import (
    get_faasm_ini_value,
    get_faasm_planner_host_port,
)
from faasmctl.util.invoke import invoke_wasm as faasmctl_invoke_wasm
from faasmctl.util.planner import reset as faasmctl_reset_planner

# TODO(planner):
from tasks.util.planner import (
    # TODO(planner):
    # get_app_result,
    get_registered_workers as get_planner_registerd_workers,
)
from time import sleep


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
        float(int(result_json["finish_ts"]) - int(result_json["start_ts"]))
        / 1000
    )

    return actual_time


def post_async_msg_and_get_result_json(msg):
    result = faasmctl_invoke_wasm(msg, dict_out=True)
    print(result)
    print(result["messageResults"])
    print(result["messageResults"][0])

    return result["messageResults"][0]


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
    faasmctl_reset_planner()
