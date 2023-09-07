from faasmctl.util.config import (
    get_faasm_ini_file,
    get_faasm_planner_host_port as faasmctl_get_planner_host_port,
)
from faasmctl.util.invoke import invoke_wasm as faasmctl_invoke_wasm


def get_faasm_exec_time_from_json(result_json):
    """
    Return the execution time (included in Faasm's response JSON) in seconds
    """
    actual_time = (
        float(int(result_json["finish_ts"]) - int(result_json["start_ts"]))
        / 1000
    )

    return actual_time


def get_faasm_planner_host_port():
    return faasmctl_get_planner_host_port(get_faasm_ini_file())


def post_async_msg_and_get_result_json(msg):
    result = faasmctl_invoke_wasm(msg, dict_out=True)

    return result["messageResults"][0]
