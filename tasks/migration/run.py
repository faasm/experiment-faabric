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


def _process_output(migration_output, result_file, nprocs, check, run_num):
    result_json = json.loads(migration_output, strict=False)
    print(
        "Processing migration output: \n{}\n".format(
            result_json["output_data"]
        )
    )
    actual_time = get_faasm_exec_time_from_json(result_json)
    with open(result_file, "a") as out_file:
        out_file.write(
            "{},{},{},{:.2f}\n".format(nprocs, check, run_num, actual_time)
        )


@task(default=True)
def run(ctx, nprocs=4, check_in=None, repeats=1):
    """
    Run migration experiment
    """
    host, port = get_faasm_invoke_host_port()

    if check_in is None:
        check_array = [0, 2, 4, 6, 8, 10]
    else:
        check_array = [int(check_in)]

    for check in check_array:
        result_file = _init_csv_file(
            "migration_{}_{}.csv".format(nprocs, check)
        )

        for run_num in range(repeats):
            # Url and headers for requests
            url = "http://{}:{}".format(host, port)

            # First, flush the host state
            print("Flushing functions, state, and shared files from workers")
            msg = {"type": MESSAGE_TYPE_FLUSH}
            print("Posting to {} msg:".format(url))
            pprint(msg)
            response = requests.post(url, json=msg, timeout=None)
            if response.status_code != 200:
                print(
                    "Flush request failed: {}:\n{}".format(
                        response.status_code, response.text
                    )
                )
            print("Waiting for flush to propagate...")
            time.sleep(5)
            print("Done waiting")

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
                "mpi_world_size": int(nprocs),
                "async": True,
                "migration_check_period": migration_check_period,
                "cmdline": "{} {}".format(
                    check if check != 0 else 5, num_loops
                ),
                "topology_hint": "{}".format(topology_hint),
            }
            print("Posting to {} msg:".format(url))
            pprint(msg)

            # Post asynch request
            response = requests.post(url, json=msg, timeout=None)
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
                time.sleep(interval)

                status_msg = {
                    "user": "mpi",
                    "function": "migrate",
                    "status": True,
                    "id": msg_id,
                }
                response = requests.post(url, json=status_msg)

                if response.text.startswith("RUNNING"):
                    continue
                elif response.text.startswith("FAILED"):
                    raise RuntimeError("Call failed")
                elif not response.text:
                    raise RuntimeError("Empty status response")
                else:
                    # If we reach this point it means the call has succeeded
                    break

            _process_output(response.text, result_file, nprocs, check, run_num)

            print("Sleeping after function is done, before flushing")
            time.sleep(5)

    print("Results written to {}".format(result_file))
