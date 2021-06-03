#!/usr/bin/python3
import json
import re
import sys

from os.path import join
from subprocess import check_output

MPI_RUN = "mpirun"
HOSTFILE = "/home/mpirun/hostfile"
LAMMPS_BUILD_PATH = "/code/experiment-lammps/third-party/lammps/install-native/bin/lmp"
LAMMPS_CMDLINE = "-in /data/in.controller"

# Benchmark details
NUM_PROCS = [4, 8, 12, 16, 20]
NUM_TESTS = 1


def get_cmdline():
    if len(sys.argv) > 1:
        return "-in {}".format(sys.argv[1])
    else:
        return LAMMPS_CMDLINE


def mpi_run(np=1, hostfile=HOSTFILE, cmdline=LAMMPS_CMDLINE):
    mpi_cmd = " ".join(
        [
            MPI_RUN,
            "-np {}".format(np),
            "-hostfile {}".format(hostfile) if hostfile else "",
            LAMMPS_BUILD_PATH,
            cmdline if cmdline else "",
        ]
    )
    print(mpi_cmd)
    output = check_output(mpi_cmd, shell=True)

    return output


def invoke(np, cmdline):
    """
    Invoke one of the ParRes Kernels functions
    """
    cmd_out = mpi_run(np=np, hostfile=HOSTFILE, cmdline=cmdline)
    cmd_out = cmd_out.decode("utf-8")
    print(cmd_out)
    return parse_out(cmd_out)


def parse_out(cmd_out):
    wall_time = re.findall("Total wall time: ([0-9:]*)", cmd_out)[0].split(":")
    time = int(wall_time[0]) * 3600 + int(wall_time[1]) * 60 + int(wall_time[2])
    return time


def benchmark():
    print("MPI LAMMPS Native Benchmark")
    results = {}

    # results are in seconds
    for np in NUM_PROCS:
        print("Running with {} MPI processes".format(np))
        if np not in results:
            results[np] = []
        for _ in range(NUM_TESTS):
            results[np].append(invoke(np, get_cmdline()))
            print("Run {}/{} finished!".format(_ + 1, NUM_TESTS))

    json.dumps(results)
    with open("/home/mpirun/results.dat", "w+") as fh:
        json.dump(results, fh)


if __name__ == "__main__":
    benchmark()
