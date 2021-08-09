import math
import re
import requests

from os import makedirs
from invoke import task
from os.path import join

from tasks.util import (
    RESULTS_DIR,
    KNATIVE_HEADERS,
)
from tasks.util.openmpi import (
    NATIVE_HOSTFILE,
    run_kubectl_cmd,
    get_pod_names_ips,
)
from tasks.kernels.env import KERNELS_FAASM_USER

ITERATIONS = 20000
SPARSE_GRID_SIZE_2LOG = 10
SPARSE_GRID_SIZE = pow(2, SPARSE_GRID_SIZE_2LOG)

NUM_PROCS = [1, 2, 3, 4, 5]

PRK_CMDLINE = {
    "dgemm": "{} 500 32 1".format(
        ITERATIONS
    ),  # iterations, matrix order, outer block size (?)
    "nstream": "{} 2000000 0".format(
        ITERATIONS
    ),  # iterations, vector length, offset
    "random": "16 16",  # update ratio, table size
    "reduce": "{} 2000000".format(ITERATIONS),  # iterations, vector length
    "sparse": "{} {} 4".format(
        ITERATIONS, SPARSE_GRID_SIZE_2LOG
    ),  # iterations, log2 grid size, stencil radius
    "stencil": "{} 1000".format(ITERATIONS),  # iterations, array dimension
    "global": "{} 10000".format(
        ITERATIONS
    ),  # iterations, scramble string length
    "p2p": "{} 1000 100".format(
        ITERATIONS
    ),  # iterations, 1st array dimension, 2nd array dimension
    "transpose": "{} 2000 64".format(
        ITERATIONS
    ),  # iterations, matrix order, tile size
}

PRK_NATIVE_BUILD = "/code/Kernels"
FAASM_WORKING_DIR = "/usr/local/code/faasm"

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
    # "dgemm": ("Avg time (s)", "Rate (MFlops/s)"),
    "nstream": ("Avg time (s)", "Rate (MB/s)"),
    # "random": ("Rate (GUPS/s)", "Time (s)"),
    "reduce": ("Rate (MFlops/s)", "Avg time (s)"),
    "sparse": ("Rate (MFlops/s)", "Avg time (s)"),
    "stencil": ("Rate (MFlops/s)", "Avg time (s)"),
    # "global": ("Rate (synch/s)", "time (s)"),
    "p2p": ("Rate (MFlops/s)", "Avg time (s)"),
    "transpose": ("Rate (MB/s)", "Avg time (s)"),
}

MPI_RUN = "mpirun"
HOSTFILE = "/home/mpirun/hostfile"


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "lammps")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("Kernel,WorldSize,Run,StatName,StatValue\n")

    return result_file


def is_power_of_two(n):
    return math.ceil(log_2(n)) == math.floor(log_2(n))


def log_2(x):
    if x == 0:
        return False

    return math.log10(x) / math.log10(2)


def _process_kernels_result(kernels_out, result_file, kernel, np, run_num):
    stats = PRK_STATS.get(kernel)

    if not stats:
        print("No stats for {}".format(kernel))
        return

    print("----- {} stats -----".format(kernel))

    for stat in stats:
        split_str = "{}: ".format(stat)
        stat_val = [c for c in kernels_out.split(split_str) if c.strip()]
        if not stat_val:
            print("{} = MISSING".format(stat))
            continue

        stat_val = stat_val[1]
        stat_val = re.split("\s+", stat_val)[0]
        stat_val = stat_val.rstrip(",")
        stat_val = float(stat_val)

        if "ime" in stat:
            return stat_val

        with open(result_file, "a") as out_file:
            out_file.write(
                "{},{},{},{},{:.2f}\n".format(
                    kernel, np, run_num, stat, stat_val
                )
            )


def _validate_function(func, np):
    if func not in PRK_CMDLINE:
        print("Invalid PRK function {}".format(func))
        exit(1)

    if func == "random" and not is_power_of_two(np):
        print("Must have a power of two number of processes for random")
        exit(1)

    elif func == "sparse" and not (SPARSE_GRID_SIZE % np == 0):
        print("To run sparse, grid size must be a multiple of --np")
        print("Currently grid_size={} and np={})".format(SPARSE_GRID_SIZE, np))
        exit(1)


@task
def wasm(ctx, host="localhost", port=8080, repeats=1, nprocs=None):
    result_file = _init_csv_file("kernels_wasm.csv")
    if nprocs:
        num_procs = [nprocs]
    else:
        num_procs = NUM_PROCS

    for func in PRK_STATS:
        for np in num_procs:
            for run_num in range(repeats):

                cmdline = PRK_CMDLINE[func]
                url = "http://{}:{}".format(host, port)
                msg = {
                    "user": KERNELS_FAASM_USER,
                    "function": func,
                    "cmdline": cmdline,
                    "mpi_world_size": np,
                }
                response = requests.post(
                    url, json=msg, headers=KNATIVE_HEADERS
                )
                if response.status_code != 200:
                    print(
                        "Invocation failed: {}:\n{}".format(
                            response.status_code, response.text
                        )
                    )
                    exit(1)

                _process_kernels_result(
                    response.text, result_file, func, np, run_num
                )


@task
def native(ctx, host="localhost", port=8080, repeats=1, nprocs=None):
    result_file = _init_csv_file("kernels_native.csv")

    if nprocs:
        num_procs = [nprocs]
    else:
        num_procs = NUM_PROCS

    pod_names, pod_ips = get_pod_names_ips("kernels")
    master_pod = pod_names[0]

    for func in PRK_STATS:
        for np in num_procs:
            for run_num in range(repeats):
                _validate_function(func, np)

                cmdline = PRK_CMDLINE[func]
                executable = PRK_NATIVE_EXECUTABLES[func]
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
                    exec_output, result_file, func, np, run_num
                )
