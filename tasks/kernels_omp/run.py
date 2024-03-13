from faasmctl.util.config import get_faasm_worker_ips
from faasmctl.util.planner import reset as reset_planner
from invoke import task
from os import makedirs
from os.path import join
from subprocess import run
from tasks.util.env import (
    OPENMP_KERNELS,
    OPENMP_KERNELS_DOCKER_DIR,
    OPENMP_KERNELS_FAASM_USER,
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from time import time

"""
from tasks.util.openmpi import (
    get_native_mpi_pods,
    run_kubectl_cmd,
)
"""

EXPECTED_NUM_VMS = 1
TOTAL_NUM_THREADS = [1, 2, 3, 4, 5, 6, 7, 8]


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "kernels-omp")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("NumThreads,Run,ExecTimeSecs\n")


def _write_csv_line(csv_name, num_threads, run, exec_time):
    result_dir = join(RESULTS_DIR, "kernels-omp")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{}\n".format(num_threads, run, exec_time))


def get_kernel_cmdline(kernel, num_threads):
    kernels_cmdline = {
        # dgemm: iterations, matrix order, tile size
        "dgemm": "10 2048 32",
        # global: iterations, scramble string length
        # string length must be multiple of num_threads
        "global": "10000 {}".format(1 * 2 * 3 * 4 * 5 * 6 * 7 * 8 * 2),
        # nstream: iterations, vector length, offset
        # nstream vector length gets OOM somewhere over 50000000 in wasm
        "nstream": "10 50000000 32",
        # p2p: iterations, 1st array dimension, 2nd array dimension
        # p2p arrays get OOM somewhere over 10000 x 10000 in wasm
        "p2p": "200 10000 10000",
        # pic: simulation steps, grid size, n particles, k, m
        "pic": [10, 1000, 5000000, 1, 0, "LINEAR", 1.0, 3.0],
        # reduce: iterations, vector length
        "reduce": "200 10000000",
        # sparse: iterations, 2log grid size, radius
        "sparse": "10 10 12",
        # stencil: iterations, array dimension
        "stencil": "10 10000",
        # transpose: iterations, matrix order, tile size
        "transpose": "10 8000 32",
    }

    return "{} {}".format(num_threads, kernels_cmdline[kernel])


def get_kernel_binary(kernel):
    return join(
        OPENMP_KERNELS_DOCKER_DIR, "build", "native", "omp_{}.o".format(kernel)
    )


def has_execution_failed(results_json):
    for result in results_json:
        if "returnValue" in result and result["returnValue"] != 0:
            return True

        if "output_data" in result:
            if "ERROR" in result["output_data"]:
                return True
            if "Call failed" in result["output_data"]:
                return True

    return False


@task
def granny(ctx, kernel=None, num_threads=None, repeats=1):
    """
    Run the OpenMP Kernels
    """
    num_vms = len(get_faasm_worker_ips())
    assert num_vms == EXPECTED_NUM_VMS, "Expected {} VMs got: {}!".format(
        EXPECTED_NUM_VMS, num_vms
    )

    if num_threads is not None:
        num_threads = [num_threads]
    else:
        num_threads = TOTAL_NUM_THREADS

    if (kernel is not None) and (kernel not in OPENMP_KERNELS):
        raise RuntimeError(
            "Unrecognised kernel ({}) must be one in: {}".format(
                kernel, OPENMP_KERNELS
            )
        )
    elif kernel is None:
        kernel = OPENMP_KERNELS
    else:
        kernel = [kernel]

    for wload in kernel:
        reset_planner(num_vms)

        csv_name = "openmp_{}_granny.csv".format(wload)
        _init_csv_file(csv_name)

        for nthread in num_threads:
            for r in range(int(repeats)):
                print(
                    "Running OpenMP Kernel ({}) with {} threads (repeat: {}/{})".format(
                        wload, nthread, r + 1, repeats
                    )
                )
                user = OPENMP_KERNELS_FAASM_USER
                func = wload
                cmdline = get_kernel_cmdline(wload, nthread)
                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                }

                result_json = post_async_msg_and_get_result_json(msg)
                actual_time = get_faasm_exec_time_from_json(
                    result_json, check=True
                )
                _write_csv_line(csv_name, nthread, r, actual_time)
                print(
                    "Kernel: {} - Nthreads: {} - Actual time: {}".format(
                        wload, nthread, actual_time
                    )
                )


@task
def native(ctx, kernel=None, num_threads=None, repeats=1):
    if num_threads is not None:
        num_threads = [num_threads]
    else:
        num_threads = TOTAL_NUM_THREADS

    if (kernel is not None) and (kernel not in OPENMP_KERNELS):
        raise RuntimeError(
            "Unrecognised kernel ({}) must be one in: {}".format(
                kernel, OPENMP_KERNELS
            )
        )
    elif kernel is None:
        kernel = OPENMP_KERNELS
    else:
        kernel = [kernel]

    # Pick one VM in the cluster at random to run native OpenMP in
    # vm_names, vm_ips = get_native_mpi_pods("openmp")
    # master_vm = vm_names[0]

    for wload in kernel:
        csv_name = "openmp_{}_native.csv".format(wload)
        _init_csv_file(csv_name)
        for r in range(int(repeats)):
            for nthread in num_threads:
                print(
                    "Running OpenMP Kernel ({}) with {} threads (repeat: {}/{})".format(
                        wload, nthread, r + 1, repeats
                    )
                )
                binary = get_kernel_binary(wload)
                cmdline = get_kernel_cmdline(wload, nthread)
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

                start_ts = time()
                # run_kubectl_cmd("openmp", exec_cmd)
                run(docker_cmd, shell=True, check=True)
                actual_time = round(time() - start_ts, 2)
                _write_csv_line(csv_name, nthread, r, actual_time)
                print("Actual time: {} s".format(actual_time))
