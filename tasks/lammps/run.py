import re
import time
import requests
from os import makedirs
from os.path import join
from invoke import task

from tasks.util import (
    RESULTS_DIR,
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_FUNC,
    DOCKER_LAMMPS_BINARY,
    KNATIVE_HEADERS,
    DOCKER_LAMMPS_DATA_FILE,
    NATIVE_HOSTFILE,
    run_kubectl_cmd,
    get_pod_names_ips,
)

DOCKER_LAMMPS_CMDLINE = "-in {}".format(DOCKER_LAMMPS_DATA_FILE)

LAMMPS_WASM_CMDLINE = "-in faasm://lammps-data/in.controller"

NUM_PROCS = [1, 2, 3, 4, 5]


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "lammps")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("WorldSize,Run,Reported,Actual\n")

    return result_file


def _process_lammps_result(
    lammps_output, result_file, num_procs, run_num, actual_time
):
    reported_time = re.findall("Total wall time: ([0-9:]*)", lammps_output)

    if len(reported_time) != 1:
        print(
            "Got {} matches for reported time, expected 1 from: \n{}".format(
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

    with open(result_file, "a") as out_file:
        out_file.write(
            "{},{},{},{:.2f}\n".format(
                num_procs, run_num, reported_time, actual_time
            )
        )


@task
def faasm(ctx, host="localhost", port=8080, repeats=1, nprocs=None):
    """
    Run the experiment on Faasm
    """
    result_file = _init_csv_file("lammps_wasm.csv")

    if nprocs:
        num_procs = [nprocs]
    else:
        num_procs = NUM_PROCS

    for np in num_procs:
        print("Running on Faasm with {} MPI processes".format(np))

        for run_num in range(repeats):
            start = time.time()

            url = "http://{}:{}".format(host, port)
            msg = {
                "user": LAMMPS_FAASM_USER,
                "function": LAMMPS_FAASM_FUNC,
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
            actual_time = end - start
            _process_lammps_result(
                response.text, result_file, np, run_num, actual_time
            )

    print("Results written to {}".format(result_file))


@task
def native(ctx, host="localhost", port=8080, repeats=1, nprocs=None):
    """
    Run the experiment natively on OpenMPI
    """
    result_file = _init_csv_file("lammps_native.csv")

    if nprocs:
        num_procs = [nprocs]
    else:
        num_procs = NUM_PROCS

    pod_names, pod_ips = get_pod_names_ips()
    master_pod = pod_names[0]

    for np in num_procs:
        print("Running natively with {} MPI processes".format(np))
        print("Chosen pod {} as master".format(master_pod))

        for run_num in range(repeats):
            start = time.time()

            mpirun_cmd = [
                "mpirun",
                "-np {}".format(np),
                "-hostfile {}".format(NATIVE_HOSTFILE),
                DOCKER_LAMMPS_BINARY,
                DOCKER_LAMMPS_CMDLINE,
            ]
            mpirun_cmd = " ".join(mpirun_cmd)

            exec_cmd = [
                "exec",
                master_pod,
                "--",
                "su mpirun -c '{}'".format(mpirun_cmd),
            ]
            exec_output = run_kubectl_cmd(" ".join(exec_cmd))
            print(exec_output)

            end = time.time()
            actual_time = end - start
            _process_lammps_result(
                exec_output, result_file, np, run_num, actual_time
            )
