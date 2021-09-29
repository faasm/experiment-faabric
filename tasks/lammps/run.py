import re
import time
import requests
from os import makedirs
from os.path import join
from invoke import task

from hoststats.client import HostStats

from tasks.util.env import (
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_knative_headers,
    get_faasm_worker_pods,
    get_faasm_invoke_host_port,
)
from tasks.util.openmpi import (
    NATIVE_HOSTFILE,
    get_native_mpi_namespace,
    get_native_mpi_pods,
    run_kubectl_cmd,
)
from tasks.lammps.env import (
    BENCHMARKS,
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_FUNC,
    DOCKER_LAMMPS_BINARY,
)

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
    print("Processing lammps output: \n{}\n".format(lammps_output))

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
def faasm(ctx, bench, repeats=1, nprocs=None, procrange=None):
    """
    Run LAMMPS experiment on Faasm
    """
    if bench not in BENCHMARKS:
        print("Unrecognized benchmark: {}".format(bench))
        print("Benchmark must be one in: {}".format(BENCHMARKS.keys()))
        exit(1)

    _bench = BENCHMARKS[bench]

    result_file = _init_csv_file(
        "lammps_wasm_{}.csv".format(_bench["out_file"])
    )

    if nprocs:
        num_procs = [nprocs]
    elif procrange:
        num_procs = range(1, int(procrange) + 1)
    else:
        num_procs = NUM_PROCS

    host, port = get_faasm_invoke_host_port()

    pod_names = get_faasm_worker_pods()
    stats = HostStats(
        pod_names,
        kubectl=True,
        kubectl_container="user-container",
        kubectl_ns="faasm",
    )

    for np in num_procs:
        print("Running on Faasm with {} MPI processes".format(np))

        for run_num in range(repeats):
            stats_csv = join(
                RESULTS_DIR,
                "lammps",
                "hoststats_wasm_{}_{}.csv".format(np, run_num),
            )

            start = time.time()
            stats.start_collection()

            file_name = _bench["data"][0].split("/")[-1]
            cmdline = "-in faasm://lammps-data/{}".format(file_name)
            url = "http://{}:{}".format(host, port)
            msg = {
                "user": LAMMPS_FAASM_USER,
                "function": LAMMPS_FAASM_FUNC,
                "cmdline": cmdline,
                "mpi_world_size": int(np),
            }
            print("Posting msg {} to {}".format(msg, url))
            knative_headers = get_knative_headers()
            response = requests.post(url, json=msg, headers=knative_headers)

            if response.status_code != 200:
                print(
                    "Invocation failed: {}:\n{}".format(
                        response.status_code, response.text
                    )
                )
                exit(1)

            end = time.time()
            actual_time = end - start

            stats.stop_and_write_to_csv(stats_csv)

            _process_lammps_result(
                response.text, result_file, np, run_num, actual_time
            )

    print("Results written to {}".format(result_file))


@task
def native(ctx, bench, repeats=1, nprocs=None, procrange=None):
    """
    Run LAMMPS experiment on OpenMPI
    """
    if bench not in BENCHMARKS:
        print("Unrecognized benchmark: {}".format(bench))
        print("Benchmark must be one in: {}".format(BENCHMARKS.keys()))
        exit(1)

    _bench = BENCHMARKS[bench]

    result_file = _init_csv_file(
        "lammps_native_{}.csv".format(_bench["out_file"])
    )

    if nprocs:
        num_procs = [nprocs]
    elif procrange:
        num_procs = range(1, int(procrange) + 1)
    else:
        num_procs = NUM_PROCS

    namespace = get_native_mpi_namespace("lammps")
    pod_names, _ = get_native_mpi_pods("lammps")
    master_pod = pod_names[0]
    stats = HostStats(pod_names, kubectl=True, kubectl_ns=namespace)

    for np in num_procs:
        print("Running natively with {} MPI processes".format(np))
        print("Chosen pod {} as master".format(master_pod))

        for run_num in range(repeats):
            stats_csv = join(
                RESULTS_DIR,
                "lammps",
                "hoststats_native_{}_{}.csv".format(np, run_num),
            )

            start = time.time()
            stats.start_collection()

            native_cmdline = "-in {}.faasm.native".format(_bench["data"][0])
            mpirun_cmd = [
                "mpirun",
                "-np {}".format(np),
                "-hostfile {}".format(NATIVE_HOSTFILE),
                DOCKER_LAMMPS_BINARY,
                native_cmdline,
            ]
            mpirun_cmd = " ".join(mpirun_cmd)

            exec_cmd = [
                "exec",
                master_pod,
                "--",
                "su mpirun -c '{}'".format(mpirun_cmd),
            ]
            exec_output = run_kubectl_cmd("lammps", " ".join(exec_cmd))
            print(exec_output)

            end = time.time()
            actual_time = end - start

            stats.stop_and_write_to_csv(stats_csv)

            _process_lammps_result(
                exec_output, result_file, np, run_num, actual_time
            )
