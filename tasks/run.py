import math
import re
import time
import requests
from os import makedirs
from os.path import join
from invoke import task

from tasks.util import (
    RESULTS_DIR,
    FAASM_USER,
    FAASM_FUNC,
    LAMMPS_DATA_FILE,
    NATIVE_INSTALL_DIR,
    NATIVE_HOSTFILE,
    run_kubectl_cmd,
    get_pod_names_ips,
)

LAMMPS_NATIVE_BINARY = join(NATIVE_INSTALL_DIR, "bin", "lmp")
LAMMPS_NATIVE_CMDLINE = "-in {}".format(LAMMPS_DATA_FILE)

LAMMPS_WASM_CMDLINE = "-in faasm://lammps-data/in.controller"

NUM_PROCS = [1, 2, 4]

KNATIVE_HEADERS = {"Host": "faasm-worker.faasm.example.com"}


def init_csv_file(csv_path):
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(csv_path, "w") as out_file:
        out_file.write("WorldSize,Reported,Actual\n")


def write_result_line(csv_path, n_procs, reported, actual):
    with open(csv_path, "w") as out_file:
        out_file.write("{},{},{}\n".format(n_procs, reported, actual))


def process_lammps_result(lammps_output, actual_time, result_file, num_procs):
    reported_time = re.findall("Total wall time: ([0-9:]*)", lammps_output)

    if len(reported_time) != 1:
        print(
            "Did not find one reported time in output. Got {} matches from: \n{}".format(
                len(reported_time), lammps_output
            )
        )
        exit(1)

    reported_time = reported_time[0].split(":")
    reported_time = (
        int(reported_time[0]) * 3600
        + int(reported_time[1]) * 60
        + int(reported_time[2])
    )

    write_result_line(result_file, num_procs, reported_time, actual_time)


@task
def faasm(ctx, host="localhost", port=8080, repeats=1, nprocs=None):
    """
    Run the experiment on Faasm
    """
    result_file = join(RESULTS_DIR, "lammps_wasm.csv")
    init_csv_file(result_file)

    if nprocs:
        num_procs = [nprocs]
    else:
        num_procs = NUM_PROCS

    for np in num_procs:
        print("Running on Faasm with {} MPI processes".format(np))

        for _ in range(repeats):
            start = time.time()

            url = "http://{}:{}".format(host, port)
            msg = {
                "user": FAASM_USER,
                "function": FAASM_FUNC,
                "cmdline": LAMMPS_WASM_CMDLINE,
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
            process_lammps_result(response.text, actual_time, result_file, np)


@task
def native(ctx, host="localhost", port=8080, repeats=1, nprocs=None):
    """
    Run the experiment natively on OpenMPI
    """
    result_file = join(RESULTS_DIR, "lammps_native.csv")
    init_csv_file(result_file)

    if nprocs:
        num_procs = [nprocs]
    else:
        num_procs = NUM_PROCS

    pod_names, pod_ips = get_pod_names_ips()
    master_pod = pod_names[0]

    for np in num_procs:
        print("Running natively with {} MPI processes".format(np))
        print("Chosen pod {} as master".format(master_pod))

        for _ in range(repeats):
            start = time.time()

            mpirun_cmd = [
                "mpirun",
                "-np",
                np,
                "-hostfile",
                NATIVE_HOSTFILE,
                LAMMPS_NATIVE_BINARY,
                LAMMPS_NATIVE_CMDLINE,
            ]
            mpirun_cmd = " ".join(mpirun_cmd)

            exec_cmd = [
                "exec",
                master_pod,
                "--",
                "\"su mpirun -c '{}'\"".format(mpirun_cmd),
            ]
            exec_output = run_kubectl_cmd(" ".join(exec_cmd))

            end = time.time()
            actual_time = math.ceil((end - start) / 60)
            process_lammps_result(exec_output, actual_time, result_file, np)
