from faasmctl.util.config import get_faasm_worker_ips
from faasmctl.util.planner import reset as reset_planner
from invoke import task
from os import makedirs
from os.path import join
from subprocess import run
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from tasks.util.lulesh import (
    LULESH_DOCKER_BINARY,
    LULESH_EXPECTED_NUM_VMS,
    LULESH_EXP_NUM_THREADS,
    LULESH_FAASM_FUNC,
    LULESH_FAASM_USER,
    LULESH_RESULTS_DIR,
    get_lulesh_cmdline,
    get_lulesh_input_data,
)
from time import time

"""
from tasks.util.openmpi import (
    get_native_mpi_pods,
    run_kubectl_cmd,
)
"""


def _init_csv_file(csv_name):
    makedirs(LULESH_RESULTS_DIR, exist_ok=True)
    result_file = join(LULESH_RESULTS_DIR, csv_name)

    with open(result_file, "w") as out_file:
        out_file.write("NumThreads,Run,ExecTimeSecs\n")

    return result_file


def _write_csv_line(csv_name, nprocs, run_num, actual_time):
    result_file = join(LULESH_RESULTS_DIR, csv_name)

    with open(result_file, "a") as out_file:
        out_file.write("{},{},{:.2f}\n".format(nprocs, run_num, actual_time))


@task(default=True)
def granny(ctx, nthreads=None, repeats=1):
    """
    Run LAMMPS simulation on Granny
    """
    num_vms = len(get_faasm_worker_ips())
    assert (
        num_vms == LULESH_EXPECTED_NUM_VMS
    ), "Expected {} VMs got: {}!".format(LULESH_EXPECTED_NUM_VMS, num_vms)

    if nthreads is None:
        nthreads = LULESH_EXP_NUM_THREADS
    else:
        nthreads = [nthreads]

    csv_name = "lulesh_granny.csv"
    _init_csv_file(csv_name)

    for nthread in nthreads:
        reset_planner(num_vms)

        for nrep in range(repeats):
            print(
                "Running LULESH on Granny with {} OpenMP threads ({}/{})".format(
                    nthread, nrep + 1, repeats
                )
            )

            # Run LULESH
            msg = {
                "user": LULESH_FAASM_USER,
                "function": LULESH_FAASM_FUNC,
                "cmdline": get_lulesh_cmdline(),
                "input_data": get_lulesh_input_data(nthread),
            }

            result_json = post_async_msg_and_get_result_json(msg)
            actual_time = get_faasm_exec_time_from_json(result_json)
            _write_csv_line(csv_name, nthread, nrep, actual_time)


@task()
def native(ctx, nthreads=None, repeats=1):
    """
    Run LAMMPS experiment on OpenMPI
    """
    if nthreads is None:
        nthreads = LULESH_EXP_NUM_THREADS
    else:
        nthreads = [nthreads]

    csv_name = "lulesh_native.csv"
    _init_csv_file(csv_name)

    # Pick one VM in the cluster at random to run native OpenMP in
    # vm_names, vm_ips = get_native_mpi_pods("openmp")
    # master_vm = vm_names[0]

    for nthread in nthreads:
        for nrep in range(repeats):
            print(
                "Running LULESH on OpenMP with {} OpenMP threads ({}/{})".format(
                    nthread, nrep + 1, repeats
                )
            )

            binary = LULESH_DOCKER_BINARY
            cmdline = get_lulesh_cmdline()
            openmp_cmd = "bash -c 'OPENMP_NUM_THREADS={} {} {}'".format(
                nthread, binary, cmdline
            )

            """
            exec_cmd = [
                "exec",
                master_vm,
                "--",
                openmp_cmd,
            ]
            exec_cmd = " ".join(exec_cmd)
            """
            docker_cmd = [
                "docker exec",
                "openmp-test",
                openmp_cmd,
            ]
            docker_cmd = " ".join(docker_cmd)

            # Run command and measure
            start_ts = time()
            # run_kubectl_cmd("openmp", exec_cmd)
            run(docker_cmd, shell=True, check=True)
            actual_time = round(time() - start_ts, 2)
            _write_csv_line(csv_name, nthread, nrep, actual_time)
            print("Actual time: {} s".format(actual_time))
