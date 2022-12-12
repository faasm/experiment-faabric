import json
import requests
import time
from invoke import task
from os import makedirs
from os.path import join
from pprint import pprint

from tasks.util.env import (
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    get_faasm_invoke_host_port,
    flush_hosts,
    post_async_msg_and_get_result_json,
)

MESSAGE_TYPE_FLUSH = 3


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "migration")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("WorldSize,Check,Run,Time\n")

    return result_file


def _write_csv_line(csv_name, nprocs, check, run_num, actual_time):
    result_dir = join(RESULTS_DIR, "migration")
    result_file = join(result_dir, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write(
            "{},{},{},{:.2f}\n".format(nprocs, check, run_num, actual_time)
        )


@task(default=True)
def run(ctx, num_cores_per_vm=8, check_in=None, repeats=1):
    """
    Run migration experiment
    """

    if check_in is None:
        check_array = [0, 2, 4, 6, 8, 10]
    else:
        check_array = [int(check_in)]

    # Url and headers for requests
    host, port = get_faasm_invoke_host_port()
    url = "http://{}:{}".format(host, port)

    for check in check_array:
        csv_name = "migration_{}_{}.csv".format(num_cores_per_vm, check)
        result_file = _init_csv_file(csv_name)

        for run_num in range(repeats):
            # First, flush the host state
            flush_hosts()

            num_loops = 100000
            # Setting a check fraction of 0 means we don't under-schedule as
            # a baseline
            if check == 0:
                migration_check_period = 0
                topology_hint = "NONE"
            else:
                migration_check_period = 2
                topology_hint = "UNDERFULL"

            msg = {
                "user": "mpi",
                "function": "migrate",
                "mpi": True,
                "mpi_world_size": int(num_cores_per_vm),
                "async": True,
                "migration_check_period": migration_check_period,
                "cmdline": "{} {}".format(
                    check if check != 0 else 5, num_loops
                ),
                "topology_hint": "{}".format(topology_hint),
            }
            result_json = post_async_msg_and_get_result_json(msg, url)
            actual_time = get_faasm_exec_time_from_json(result_json)
            _write_csv_line(csv_name, num_cores_per_vm, check, run_num, actual_time)

            print("Sleeping after function is done, before flushing")
            time.sleep(5)

    print("Results written to {}".format(result_file))
