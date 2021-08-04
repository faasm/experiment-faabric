import math
import re
import time
import requests
from os import makedirs
from os.path import join
from invoke import task

from tasks.util import RESULTS_DIR, FAASM_USER, FAASM_FUNC

LAMMPS_CMDLINE = "-in faasm://lammps-data/in.controller"

NUM_PROCS = [1, 2, 4]

KNATIVE_HEADERS = {"Host": "faasm-worker.faasm.example.com"}


def init_csv_file(csv_path):
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(csv_path, "w") as out_file:
        out_file.write("WorldSize,Reported,Actual\n")


def write_result_line(csv_path, n_procs, reported, actual):
    with open(csv_path, "w") as out_file:
        out_file.write("{},{},{}\n".format(n_procs, reported, actual))


@task
def faasm(ctx, host="localhost", port=8080, repeats=1, nprocs=None):
    """
    Run the experiment on Faasm
    """
    results = {}
    result_file = join(RESULTS_DIR, "lammps_wasm.csv")
    init_csv_file(result_file)

    if nprocs:
        num_procs = [nprocs]
    else:
        num_procs = NUM_PROCS

    for np in num_procs:
        print("Running on Faasm with {} MPI processes".format(np))

        if np not in results:
            results[np] = []
        for _ in range(repeats):
            start = time.time()

            url = "http://{}:{}".format(host, port)
            msg = {
                "user": FAASM_USER,
                "function": FAASM_FUNC,
                "cmdline": LAMMPS_CMDLINE,
                "mpi_world_size": np,
            }
            print("Posting to {}".format(url))
            response = requests.post(url, json=msg, headers=KNATIVE_HEADERS)

            if response.status_code != 200:
                print(
                    "Invocation failed: {}:\n{}".format(
                        response.status_code, response.text
                    )
                )
                exit(1)

            end = time.time()
            actual_time = math.ceil((end - start) / 60)
            print("Elapsed mins: {}".format(actual_time))

            reported_time = re.findall(
                "Total wall time: ([0-9:]*)", response.text
            )

            if len(reported_time) != 1:
                print(
                    "Did not find one reported time in output. Got {} matches from: \n{}".format(
                        len(reported_time), response.text
                    )
                )
                exit(1)

            reported_time = reported_time[0].split(":")
            reported_time = (
                int(reported_time[0]) * 3600
                + int(reported_time[1]) * 60
                + int(reported_time[2])
            )

            write_result_line(result_file, np, reported_time, actual_time)
