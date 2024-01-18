from faasmctl.util.flush import flush_workers
from faasmctl.util.invoke import invoke_wasm as faasmctl_invoke_wasm
from invoke import task
from os import makedirs
from os.path import join
from subprocess import run
from tasks.util.env import (
    DGEMM_DOCKER_BINARY,
    DGEMM_FAASM_USER,
    DGEMM_FAASM_FUNC,
    OPENMP_KERNELS,
    OPENMP_KERNELS_DOCKER_DIR,
    OPENMP_KERNELS_FAASM_USER,
    RESULTS_DIR,
)
from tasks.util.faasm import get_faasm_exec_time_from_json
from time import time

# TODO: move this to tasks.openmp.env
from tasks.makespan.env import (
    get_dgemm_cmdline,
)

"""
from tasks.util.openmpi import (
    get_native_mpi_pods,
    run_kubectl_cmd,
)
"""

TOTAL_NUM_THREADS = [1, 2, 3, 4, 5, 6, 7, 8]


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "openmp")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("NumThreads,Run,ExecTimeSecs\n")


def _write_csv_line(csv_name, num_threads, run, exec_time):
    result_dir = join(RESULTS_DIR, "openmp")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{}\n".format(num_threads, run, exec_time))


def get_kernel_cmdline(kernel, num_threads):
    kernels_cmdline = {
        # dgemm: iterations, matrix order, tile size
        "dgemm": [10, 2048, 32],
        # global: iterations, scramble string length
        "global": "10000 100000",
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
        "sparse": [10, 10, 12],
        # stencil: iterations, array dimension
        "stencil": [10, 10000],
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
def granny(ctx, workload="dgemm", num_threads=None, repeats=1):
    if num_threads is not None:
        num_threads = [num_threads]
    else:
        num_threads = TOTAL_NUM_THREADS  # [1, 2, 3, 4, 5, 6, 7, 8]

    all_workloads = ["dgemm"]
    if workload not in OPENMP_KERNELS:
        raise RuntimeError(
            "Unrecognised workload ({}) must be one in: {}".format(
                workload, all_workloads
            )
        )
    elif workload == "all":
        workload = all_workloads
    else:
        workload = [workload]

    for wload in workload:
        for nthread in num_threads:
            for r in range(int(repeats)):
                csv_name = "openmp_{}_granny_{}.csv".format(wload, num_threads)
                _init_csv_file(csv_name)

                flush_workers()

                if wload == "dgemm":
                    user = DGEMM_FAASM_USER
                    func = DGEMM_FAASM_FUNC
                    cmdline = get_dgemm_cmdline(nthread, iterations=4)  # 20)
                else:
                    user = OPENMP_KERNELS_FAASM_USER
                    func = wload
                    cmdline = get_kernel_cmdline(wload, nthread)
                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                }
                req = {
                    "user": user,
                    "function": func,
                    "singleHost": True,
                }
                if wload == "lulesh":
                    msg["input_data"] = str(nthread)

                # result_json = post_async_msg_and_get_result_json(msg)
                results_json = faasmctl_invoke_wasm(
                    msg, req_dict=req, dict_out=True
                )["messageResults"]
                while has_execution_failed(results_json):
                    print("Execution failed, trying again...")
                    return
                    # print(results_json)
                    # print(result_json)
                    results_json = faasmctl_invoke_wasm(
                        msg, req_dict=req, dict_out=True
                    )["messageResults"]

                result_json = results_json[0]

                actual_time = int(get_faasm_exec_time_from_json(result_json))
                _write_csv_line(csv_name, nthread, r, actual_time)
                print(
                    "Nthreads: {} - Actual time: {}".format(
                        nthread, actual_time
                    )
                )


@task
def native(ctx, workload="dgemm", num_threads=None, repeats=1):
    if num_threads is not None:
        num_threads = [num_threads]
    else:
        num_threads = TOTAL_NUM_THREADS

    all_workloads = ["dgemm", "lulesh", "all"]
    if workload not in OPENMP_KERNELS:
        raise RuntimeError(
            "Unrecognised workload ({}) must be one in: {}".format(
                workload, all_workloads
            )
        )
    elif workload == "all":
        workload = ["dgemm", "lulesh"]
    else:
        workload = [workload]

    # Pick one VM in the cluster at random to run native OpenMP in
    # vm_names, vm_ips = get_native_mpi_pods("openmp")
    # master_vm = vm_names[0]

    for wload in workload:
        csv_name = "openmp_{}_native.csv".format(wload)
        _init_csv_file(csv_name)
        for r in range(int(repeats)):
            for nthread in num_threads:
                if wload == "dgemm":
                    binary = DGEMM_DOCKER_BINARY
                    cmdline = get_dgemm_cmdline(nthread, iterations=20)
                else:
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
                actual_time = int(time() - start_ts)
                _write_csv_line(csv_name, nthread, r, actual_time)
                print("Actual time: {}".format(actual_time))
