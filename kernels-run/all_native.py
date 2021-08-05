#!/usr/bin/python3
import json
import math
import re
import sys

from os.path import join
from subprocess import check_output, DEVNULL

FAASM_USER = "prk"
ITERATIONS = 20000
SPARSE_GRID_SIZE_2LOG = 10
SPARSE_GRID_SIZE = pow(2, SPARSE_GRID_SIZE_2LOG)

PRK_CMDLINE = {
    "dgemm": "{} 500 32 1".format(
        ITERATIONS
    ),  # iterations, matrix order, outer block size (?)
    "nstream": "{} 2000000 0".format(ITERATIONS),  # iterations, vector length, offset
    "random": "16 16",  # update ratio, table size
    "reduce": "{} 2000000".format(ITERATIONS),  # iterations, vector length
    "sparse": "{} {} 4".format(
        ITERATIONS, SPARSE_GRID_SIZE_2LOG
    ),  # iterations, log2 grid size, stencil radius
    "stencil": "{} 1000".format(ITERATIONS),  # iterations, array dimension
    "global": "{} 10000".format(ITERATIONS),  # iterations, scramble string length
    "p2p": "{} 1000 100".format(
        ITERATIONS
    ),  # iterations, 1st array dimension, 2nd array dimension
    "transpose": "{} 2000 64".format(ITERATIONS),  # iterations, matrix order, tile size
}

PRK_NATIVE_BUILD = "/code/Kernels"

PRK_NATIVE_EXECUTABLES = {
    # "dgemm": join(PRK_NATIVE_BUILD, "MPI1", "DGEMM", "dgemm"),
    "nstream": join(PRK_NATIVE_BUILD, "MPI1", "Nstream", "nstream"),
    # "random": join(PRK_NATIVE_BUILD, "MPI1", "Random", "random"),
    "reduce": join(PRK_NATIVE_BUILD, "MPI1", "Reduce", "reduce"),
    "sparse": join(PRK_NATIVE_BUILD, "MPI1", "Sparse", "sparse"),
    "stencil": join(PRK_NATIVE_BUILD, "MPI1", "Stencil", "stencil"),
    # "global": join(PRK_NATIVE_BUILD, "MPI1", "Synch_global", "global"),
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


def is_power_of_two(n):
    return math.ceil(log_2(n)) == math.floor(log_2(n))


def log_2(x):
    if x == 0:
        return False

    return math.log10(x) / math.log10(2)


def mpi_run(exe, np=1, hostfile=None, cmdline=None):
    mpi_cmd = " ".join(
        [
            MPI_RUN,
            "-np {}".format(np),
            "-hostfile {}".format(hostfile) if hostfile else "",
            exe,
            cmdline if cmdline else "",
        ]
    )
    print(mpi_cmd)
    output = check_output(mpi_cmd, shell=True)

    return output


def invoke(func, np=8):
    """
    Invoke one of the ParRes Kernels functions
    """
    if func not in PRK_CMDLINE:
        print("Invalid PRK function {}".format(func))
        return 1

    cmdline = PRK_CMDLINE[func]

    if func == "random" and not is_power_of_two(np):
        print("Must have a power of two number of processes for random")
        exit(1)
    elif func == "sparse" and not (SPARSE_GRID_SIZE % np == 0):
        print(
            "To run sparse, grid size must be a multiple of --np (currently grid_size={} and np={})".format(
                SPARSE_GRID_SIZE, np
            )
        )
        exit(1)

    executable = PRK_NATIVE_EXECUTABLES[func]
    cmd_out = mpi_run(executable, np=np, hostfile=HOSTFILE, cmdline=cmdline)
    cmd_out = cmd_out.decode()
    print(cmd_out)

    return _parse_prk_out(func, cmd_out)


def _parse_prk_out(func, cmd_out):
    stats = PRK_STATS.get(func)

    if not stats:
        print("No stats for {}".format(func))
        return

    print("----- {} stats -----".format(func))

    for stat in stats:
        spilt_str = "{}: ".format(stat)

        stat_val = [c for c in cmd_out.split(spilt_str) if c.strip()]
        if not stat_val:
            print("{} = MISSING".format(stat))
            continue

        stat_val = stat_val[1]
        stat_val = re.split("\s+", stat_val)[0]
        stat_val = stat_val.rstrip(",")
        stat_val = float(stat_val)

        if "ime" in stat:
            return stat_val


if __name__ == "__main__":
    # procs = [1, 2, 4, 8, 16]
    procs = [1, 2, 4]
    results = {}

    # results are in seconds
    for func in PRK_STATS:
        if func not in results:
            results[func] = []
        for np in procs:
            results[func].append(invoke(func, np))

    print(json.dumps(results))
    with open("./results.dat", "w") as fh:
        json.dump(results, fh)
