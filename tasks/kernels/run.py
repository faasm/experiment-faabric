from faasmctl.util.flush import flush_workers
from invoke import task
from math import ceil, floor, log10
from os import makedirs
from os.path import join
from tasks.util.env import (
    KERNELS_FAASM_FUNCS,
    KERNELS_FAASM_USER,
    KERNELS_NATIVE_DIR,
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from tasks.util.openmpi import (
    run_kubectl_cmd,
    get_native_mpi_pods,
)
from time import time


def is_power_of_two(n):
    return ceil(log_2(n)) == floor(log_2(n))


def log_2(x):
    if x == 0:
        return False

    return log10(x) / log10(2)


def get_kernels_cmdline(kernel_name, np):
    if kernel_name not in KERNELS_FAASM_FUNCS:
        raise RuntimeError(
            "Kernel {} not supported. Available: {}".format(
                kernel_name, KERNELS_FAASM_FUNCS
            )
        )

    transpose_matrix_order = 2 * 4 * 5 * 6 * 7
    sparse_grid_size_log2 = 10
    sparse_grid_size = pow(2, sparse_grid_size_log2)

    if kernel_name == "random" and not is_power_of_two(np):
        raise RuntimeError(
            "Must have a power of two number of processes for random"
        )
    elif kernel_name == "sparse" and not (sparse_grid_size % np == 0):
        print("To run sparse, grid size must be a multiple of --np")
        print("Currently grid_size={} and np={})".format(sparse_grid_size, np))
        raise RuntimeError("Incorrect command line parameters for 'sparse'")
    elif kernel_name == "transpose" and not (transpose_matrix_order % np == 0):
        raise RuntimeError(
            "# proc must divide transpose matrix order ({})".format(
                transpose_matrix_order
            )
        )

    prk_cmdline = {
        "dgemm": "1000 500 32 1",
        # dgemm: iterations, matrix order, outer block size
        "nstream": "2000000 200000 0",
        # nstream: iterations, vector length, offset
        "random": "16 16",  # update ratio, table size
        "reduce": "40000 20000",
        # reduce: iterations, vector length
        "sparse": "400 {} 4".format(sparse_grid_size_log2),
        # sparse: iterations, log2 grid size, stencil radius
        "stencil": "20000 1000",
        # stencil: iterations, array dimension
        "global": "1000 10000",
        # global: iterations, scramble string length
        "p2p": "10000 10000 1000",
        # p2p: iterations, 1st array dimension, 2nd array dimension
        "transpose": "500 {} 64".format(transpose_matrix_order),
        # transpose: iterations, matrix order, tile size
        # notes:
        # - matrix order must be a multiple of # procs
        # - if iterations > 500, result overflows
    }

    return prk_cmdline[kernel_name]


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "mpi")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("WorldSize,Run,ActualTime\n")


def _write_csv_line(csv_name, num_procs, run, exec_time):
    result_dir = join(RESULTS_DIR, "mpi")
    result_file = join(result_dir, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{}\n".format(num_procs, run, exec_time))


@task
def granny(ctx, repeats=1, num_procs=None, kernel=None):
    """
    Run the kernels benchmark in faasm
    """
    # First, work out the number of processes to run with
    if num_procs is not None:
        num_procs = [int(num_procs)]
    else:
        num_procs = [2, 4, 6, 8, 10, 12, 14, 16]

    if kernel:
        if kernel == "all":
            kernels = KERNELS_FAASM_FUNCS
        else:
            kernels = [kernel]
    else:
        kernels = KERNELS_FAASM_FUNCS

    for kernel in kernels:
        csv_name = "kernels_granny_{}.csv".format(kernel)
        _init_csv_file(csv_name)

        for run_num in range(repeats):
            for np in num_procs:
                # Flush the cluster fist
                flush_workers()

                try:
                    cmdline = get_kernels_cmdline(kernel, np)
                except RuntimeError as e:
                    if kernel == "sparse":
                        print("Skipping sparse kernel for np: {}".format(np))
                        continue
                    raise e
                user = KERNELS_FAASM_USER
                func = kernel
                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                    "mpi": True,
                    "mpi_world_size": np,
                    "async": True,
                }
                result_json = post_async_msg_and_get_result_json(msg)
                actual_time = int(get_faasm_exec_time_from_json(result_json))
                _write_csv_line(csv_name, np, run_num, actual_time)
                print("Actual time: {}".format(actual_time))


@task
def native(ctx, repeats=1, num_procs=None, kernel=None):
    """
    Run Kernels benchmark natively
    """
    # First, work out the number of processes to run with
    if num_procs is not None:
        num_procs = [int(num_procs)]
    else:
        num_procs = [2, 4, 6, 8, 10, 12, 14, 16]

    if kernel:
        if kernel == "all":
            kernels = KERNELS_FAASM_FUNCS
        else:
            kernels = [kernel]
    else:
        kernels = KERNELS_FAASM_FUNCS

    # Pick one VM in the cluster at random to run native OpenMP in
    vm_names, vm_ips = get_native_mpi_pods("makespan")
    master_vm = vm_names[0]
    master_ip = vm_ips[0]
    worker_ip = vm_ips[1]

    for kernel in kernels:
        csv_name = "kernels_native_{}.csv".format(kernel)
        _init_csv_file(csv_name)
        binary = join(KERNELS_NATIVE_DIR, "mpi_{}.o".format(kernel))

        for run_num in range(repeats):
            for np in num_procs:
                try:
                    cmdline = get_kernels_cmdline(kernel, np)
                except RuntimeError as e:
                    if kernel == "sparse":
                        print("Skipping sparse kernel for np: {}".format(np))
                        continue
                    raise e

                # Work out an allocation list to avoid having to copy hostfiles
                num_cores_per_ctr = 8
                allocated_pod_ips = []
                if np > num_cores_per_ctr:
                    allocated_pod_ips = [
                        "{}:{}".format(master_ip, num_cores_per_ctr),
                        "{}:{}".format(worker_ip, np - num_cores_per_ctr),
                    ]
                else:
                    allocated_pod_ips = ["{}:{}".format(master_ip, np)]
                mpirun_cmd = [
                    "mpirun",
                    "-np {}".format(np),
                    "-host {}".format(",".join(allocated_pod_ips)),
                    binary,
                    cmdline,
                ]
                mpirun_cmd = " ".join(mpirun_cmd)

                exec_cmd = [
                    "exec",
                    master_vm,
                    "--",
                    "su mpirun -c '{}'".format(mpirun_cmd),
                ]
                exec_cmd = " ".join(exec_cmd)

                start_ts = time()
                run_kubectl_cmd("makespan", exec_cmd)
                actual_time = int(time() - start_ts)
                _write_csv_line(csv_name, np, run_num, actual_time)
                print("Actual time: {}".format(actual_time))
