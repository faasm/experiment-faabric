#!/usr/bin/python3
import json
import math
import re
import sys
import time

from os import environ
from os.path import dirname, join, realpath
from subprocess import check_output

from faasmcli.util.call import invoke_impl

PROJ_ROOT = dirname(dirname(realpath(__file__)))
BASE_DIR = "{}/../..".format(PROJ_ROOT)
LAMMPS_USR = "lammps"
LAMMPS_FUNC = "main"
LAMMPS_CMDLINE = "-in faasm://lammps-data/in.controller"

# Benchmark details
# TODO decide where common config may live
NUM_PROCS = [1, 2, 4]
NUM_TESTS = 1


# Update k8s host and port env variables
def update_env():
    _out = check_output(
        "{}/faasm/bin/knative_route.sh | tail -6".format(BASE_DIR), shell=True
    )
    out = _out.decode("utf-8").strip().split("\n")

    # Prepare dict
    new_env = {}
    for var in out:
        new_env[var.split(" ")[0].upper()] = var.split(" ")[2]

    # Update environment
    environ.update(new_env)


def invoke(np):
    """
    Invoke one LAMMPS execution
    """
    start = time.time()
    cmd_out = invoke_impl(
        LAMMPS_USR, LAMMPS_FUNC, mpi_world_size=np, cmdline=LAMMPS_CMDLINE, debug=True
    )
    print(cmd_out)
    elapsed_mins = math.ceil((time.time() - start) / 60)
    print("Elapsed mins: {}".format(elapsed_mins))

    return parse_output(elapsed_mins)


def benchmark():
    print("MPI LAMMPS Native Benchmark")
    results = {}

    # Update env. variables
    update_env()

    # results are in seconds
    for np in NUM_PROCS:
        print("Running with {} MPI processes".format(np))
        if np not in results:
            results[np] = []
        for _ in range(NUM_TESTS):
            results[np].append(invoke(np))
            print("Run {}/{} finished!".format(_ + 1, NUM_TESTS))

    json.dumps(results)
    with open("{}/results/lammps/lammps_faasm.dat".format(BASE_DIR), "w+") as fh:
        json.dump(results, fh)


def parse_output(elapsed_mins):
    # Get kubectl logs
    _kubectl_cmd = [
        "kubectl logs -n faasm",
        "--since={}m".format(elapsed_mins),
        "--tail=-1",
        "-l serving.knative.dev/service=faasm-worker",
        "-c user-container",
    ]

    kubectl_cmd = " ".join(_kubectl_cmd)
    out = check_output(kubectl_cmd, shell=True).decode("utf-8")
    print(out)

    # Parse the logs
    # Note that given that we can't clear k8s logs, it may happen that we find
    # two consecutive results (as we query logs w/ 1' granularity). Hence, we
    # pick the most recent match.
    wall_time = re.findall("Total wall time: ([0-9:]*)", out)[-1].split(":")
    time = int(wall_time[0]) * 3600 + int(wall_time[1]) * 60 + int(wall_time[2])

    print(time)
    return time


if __name__ == "__main__":
    benchmark()
