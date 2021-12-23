import json
import math
import requests
import time

from os import makedirs
from invoke import task
from os.path import join
from pprint import pprint

from tasks.util.env import (
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    get_faasm_invoke_host_port,
    get_knative_headers,
)
from tasks.util.openmpi import (
    NATIVE_HOSTFILE,
    run_kubectl_cmd,
    get_native_mpi_pods,
)
from tasks.kernels.env import KERNELS_FAASM_USER

MESSAGE_TYPE_FLUSH = 3
NUM_PROCS = [2, 4, 8, 16]

SPARSE_GRID_SIZE_2LOG = 10
SPARSE_GRID_SIZE = pow(2, SPARSE_GRID_SIZE_2LOG)

PRK_CMDLINE = {
    "dgemm": "1000 500 32 1",
    # dgemm: iterations, matrix order, outer block size
    "nstream": "2000000 200000 0",
    # nstream: iterations, vector length, offset
    "random": "16 16",  # update ratio, table size
    "reduce": "40000 2000",
    # reduce: iterations, vector length
    "sparse": "400 10 4",
    # sparse: iterations, log2 grid size, stencil radius
    "stencil": "20000 1000",
    # stencil: iterations, array dimension
    "global": "1000 10000",
    # global: iterations, scramble string length
    "p2p": "10000 10000 1000",
    # p2p: iterations, 1st array dimension, 2nd array dimension
    "transpose": "500 2000 64",  # if iterations > 500, result overflows
    # transpose: iterations, matrix order, tile size
}

PRK_NATIVE_BUILD = "/code/experiment-mpi/third-party/kernels-native"

PRK_NATIVE_EXECUTABLES = {
    "dgemm": join(PRK_NATIVE_BUILD, "MPI1", "DGEMM", "dgemm"),
    "nstream": join(PRK_NATIVE_BUILD, "MPI1", "Nstream", "nstream"),
    "random": join(PRK_NATIVE_BUILD, "MPI1", "Random", "random"),
    "reduce": join(PRK_NATIVE_BUILD, "MPI1", "Reduce", "reduce"),
    "sparse": join(PRK_NATIVE_BUILD, "MPI1", "Sparse", "sparse"),
    "stencil": join(PRK_NATIVE_BUILD, "MPI1", "Stencil", "stencil"),
    "global": join(PRK_NATIVE_BUILD, "MPI1", "Synch_global", "global"),
    "p2p": join(PRK_NATIVE_BUILD, "MPI1", "Synch_p2p", "p2p"),
    "transpose": join(PRK_NATIVE_BUILD, "MPI1", "Transpose", "transpose"),
}

PRK_STATS = {
    # "dgemm": ("Avg time (s)", "Rate (MFlops/s)"), uses MPI_Group_incl
    # "nstream": ("Avg time (s)", "Rate (MB/s)"),
    # "random": ("Rate (GUPS/s)", "Time (s)"), uses MPI_Alltoallv
    "reduce": ("Rate (MFlops/s)", "Avg time (s)"),
    "sparse": ("Rate (MFlops/s)", "Avg time (s)"),
    # "stencil": ("Rate (MFlops/s)", "Avg time (s)"),
    # "global": ("Rate (synch/s)", "time (s)"), uses MPI_Type_commit
    "p2p": ("Rate (MFlops/s)", "Avg time (s)"),
    "transpose": ("Rate (MB/s)", "Avg time (s)"),
}

MPI_RUN = "mpirun"
HOSTFILE = "/home/mpirun/hostfile"


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "kernels")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("Kernel,WorldSize,Run,StatName,StatValue,ActualTime\n")

    return result_file


def is_power_of_two(n):
    return math.ceil(log_2(n)) == math.floor(log_2(n))


def log_2(x):
    if x == 0:
        return False

    return math.log10(x) / math.log10(2)


def _process_kernels_result(
    result_txt, result_file, kernel, np, run_num, measured_time=None
):
    stats = PRK_STATS.get(kernel)

    if not stats:
        print("No stats for {}".format(kernel))
        return

    # Prepare response output and elapsed time
    if "wasm" in result_file:
        result_json = json.loads(result_txt, strict=False)
        kernels_out = result_json["output_data"]
        real_time = get_faasm_exec_time_from_json(result_json)
    else:
        kernels_out = result_txt
        if measured_time == None:
            raise RuntimeError("Empty measured time for non-WASM execution")
        real_time = measured_time

    # First, get real executed time from response text
    print("Actual time: {}".format(real_time))

    # Then, process the output text
    for stat in stats:
        stat_parts = kernels_out.split(stat)
        stat_parts = [s for s in stat_parts if s.strip()]
        if len(stat_parts) < 2:
            print(
                "WARNING: Could not find stat {} for kernel {} in output".format(
                    stat, kernel
                )
            )
            return

        stat_val = stat_parts[-1].replace(":", "")
        stat_val = [s.strip() for s in stat_val.split(" ") if s.strip()]
        stat_val = stat_val[0]
        print("Got {} = {} for {}".format(stat, stat_val, kernel))

        stat_val = float(stat_val)
        with open(result_file, "a") as out_file:
            out_file.write(
                "{},{},{},{},{:.8f},{:.8f}\n".format(
                    kernel, np, run_num, stat, stat_val, real_time
                )
            )


def _validate_kernel(kernel, np):
    if kernel not in PRK_CMDLINE:
        print("Invalid PRK function {}".format(kernel))
        exit(1)

    if kernel == "random" and not is_power_of_two(np):
        print("Must have a power of two number of processes for random")
        exit(1)

    elif kernel == "sparse" and not (SPARSE_GRID_SIZE % np == 0):
        print("To run sparse, grid size must be a multiple of --np")
        print("Currently grid_size={} and np={})".format(SPARSE_GRID_SIZE, np))
        exit(1)


@task
def faasm(ctx, repeats=1, nprocs=None, kernel=None, procrange=None):
    """
    Run the kernels benchmark in faasm
    """

    # First, work out the number of processes to run with
    if nprocs:
        num_procs = [nprocs]
    elif procrange:
        num_procs = range(1, int(procrange) + 1)
    else:
        num_procs = NUM_PROCS

    if kernel:
        kernels = [kernel]
    else:
        kernels = PRK_STATS.keys()

    host, port = get_faasm_invoke_host_port()

    for kernel in kernels:
        result_file = _init_csv_file("kernels_wasm_{}.csv".format(kernel))

        for np in num_procs:
            np = int(np)
            _validate_kernel(kernel, np)
            for run_num in range(repeats):
                # Url and header for request
                url = "http://{}:{}".format(host, port)
                knative_headers = get_knative_headers()

                # First, flush the host state
                print(
                    "Flushing functions, state, and shared files from workers"
                )
                msg = {"type": MESSAGE_TYPE_FLUSH}
                print("Posting to {} msg:".format(url))
                pprint(msg)
                response = requests.post(
                    url, json=msg, headers=knative_headers, timeout=None
                )
                if response.status_code != 200:
                    print(
                        "Flush request failed: {}:\n{}".format(
                            response.status_code, response.text
                        )
                    )
                print("Waiting for flush to propagate...")
                time.sleep(5)
                print("Done waiting")

                cmdline = PRK_CMDLINE[kernel]
                msg = {
                    "user": KERNELS_FAASM_USER,
                    "function": kernel,
                    "cmdline": cmdline,
                    "mpi_world_size": np,
                    "async": True,
                }
                print("Posting to {} msg:".format(url))
                pprint(msg)

                # Post asynch request
                response = requests.post(
                    url, json=msg, headers=knative_headers, timeout=None
                )
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
                        "user": KERNELS_FAASM_USER,
                        "function": kernel,
                        "status": True,
                        "id": msg_id,
                    }
                    response = requests.post(
                        url,
                        json=status_msg,
                        headers=knative_headers,
                    )

                    if response.text.startswith("RUNNING"):
                        print(response.text)
                        continue
                    elif response.text.startswith("FAILED"):
                        raise RuntimeError("Call failed")
                    elif not response.text:
                        raise RuntimeError("Empty status response")
                    else:
                        # If we reach this point it means the call has succeeded
                        break

                _process_kernels_result(
                    response.text,
                    result_file,
                    kernel,
                    np,
                    run_num,
                )


@task
def native(ctx, repeats=1, nprocs=None, kernel=None, procrange=None):
    if nprocs:
        num_procs = [nprocs]
    elif procrange:
        num_procs = range(1, int(procrange) + 1)
    else:
        num_procs = NUM_PROCS

    pod_names, pod_ips = get_native_mpi_pods("kernels")
    master_pod = pod_names[0]

    if kernel:
        kernels = [kernel]
    else:
        kernels = PRK_STATS.keys()

    for kernel in kernels:
        result_file = _init_csv_file("kernels_native_{}.csv".format(kernel))

        for np in num_procs:
            for run_num in range(repeats):
                np = int(np)
                _validate_kernel(kernel, np)

                start = time.time()
                cmdline = PRK_CMDLINE[kernel]
                executable = PRK_NATIVE_EXECUTABLES[kernel]
                mpirun_cmd = [
                    "mpirun",
                    "-np {}".format(np),
                    "-hostfile {}".format(NATIVE_HOSTFILE),
                    executable,
                    cmdline,
                ]
                mpirun_cmd = " ".join(mpirun_cmd)

                exec_cmd = [
                    "exec",
                    master_pod,
                    "--",
                    "su mpirun -c '{}'".format(mpirun_cmd),
                ]
                exec_output = run_kubectl_cmd("kernels", " ".join(exec_cmd))
                print(exec_output)

                _process_kernels_result(
                    exec_output,
                    result_file,
                    kernel,
                    np,
                    run_num,
                    time.time() - start,
                )
