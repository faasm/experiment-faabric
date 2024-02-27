from faasmctl.util.config import (
    get_faasm_ini_file,
    get_faasm_planner_host_port as faasmctl_get_planner_host_port,
)
from faasmctl.util.invoke import invoke_wasm as faasmctl_invoke_wasm
from os import environ


def get_faasm_exec_time_from_json(results_json, check=False):
    """
    Return the execution time (included in Faasm's response JSON) in seconds
    """
    start_ts = min([result_json["start_ts"] for result_json in results_json])
    finish_ts = max([result_json["finish_ts"] for result_json in results_json])

    actual_time = float(int(finish_ts) - int(start_ts)) / 1000

    return actual_time


def get_faasm_planner_host_port():
    return faasmctl_get_planner_host_port(get_faasm_ini_file())


def get_faasm_version():
    if "FAASM_VERSION" in environ:
        return environ["FAASM_VERSION"]

    return "0.0.0"


def post_async_msg_and_get_result_json(msg, host_list=None):
    result = faasmctl_invoke_wasm(msg, dict_out=True, host_list=host_list)

    return result["messageResults"]
