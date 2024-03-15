from faasmctl.util.config import get_faasm_worker_ips
from faasmctl.util.planner import reset as reset_planner
from invoke import task
from math import ceil, floor, log10
from os import makedirs
from os.path import join
from tasks.util.kernels import (
    KERNELS_NATIVE_DIR,
    MPI_KERNELS_FAASM_FUNCS,
    MPI_KERNELS_FAASM_USER,
    MPI_KERNELS_EXPERIMENT_NPROCS,
    MPI_KERNELS_RESULTS_DIR,
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

EXPECTED_NUM_VMS = 2


def is_power_of_two(n):
    return ceil(log_2(n)) == floor(log_2(n))


def log_2(x):
    if x == 0:
        return False

    return log10(x) / log10(2)


def get_kernels_cmdline(kernel_name, np):
    if kernel_name not in MPI_KERNELS_FAASM_FUNCS:
        raise RuntimeError(
            "Kernel {} not supported. Available: {}".format(
                kernel_name, MPI_KERNELS_FAASM_FUNCS
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
        # branch: iterations, loop length, branching type
        "branch": "10 10 vector_go",
        # dgemm: iterations, matrix order, outer block size
        "dgemm": "1000 500 32 1",
        # nstream: iterations, vector length, offset
        "nstream": "2000000 200000 0",
        "random": "16 16",
        # random: update ratio, table size
        "reduce": "40000 2000",
        # reduce: iterations, vector length
        "sparse": "400 {} 4".format(sparse_grid_size_log2),
        # sparse: iterations, log2 grid size, stencil radius
        "stencil": "20000 1000",
        # stencil: iterations, array dimension
        "global": "1000 10000",
        # global: iterations, scramble string length
        "p2p": "1000 1024 1024",
        # p2p: iterations, 1st array dimension, 2nd array dimension
        "transpose": "600 {} 64".format(transpose_matrix_order),
        # transpose: iterations, matrix order, tile size
        # notes:
        # - matrix order must be a multiple of # procs
        # - if iterations > 500, result overflows
    }

    return prk_cmdline[kernel_name]


def _init_csv_file(csv_name):
    makedirs(MPI_KERNELS_RESULTS_DIR, exist_ok=True)
    result_file = join(MPI_KERNELS_RESULTS_DIR, csv_name)
    with open(result_file, "w") as out_file:
        out_file.write("WorldSize,Run,ActualTime\n")


def _write_csv_line(csv_name, num_procs, run, exec_time):
    result_file = join(MPI_KERNELS_RESULTS_DIR, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{}\n".format(num_procs, run, exec_time))


def print_exp_status(
    baseline,
    kernel,
    np,
    ind_kernel,
    len_kernels,
    ind_np,
    len_nps,
    run_num,
    repeats,
):
    print(
        "Running MPI Kernel ({}) on {} with {} MPI processes"
        " (kernel: {}/{}, MPI procs: {}/{}, repeat: {}/{})".format(
            kernel,
            baseline,
            np,
            ind_kernel + 1,
            len_kernels,
            ind_np + 1,
            len_nps,
            run_num + 1,
            repeats,
        )
    )


@task
def wasm(ctx, repeats=1, num_procs=None, kernel=None):
    """
    Run the MPI Kernels (WASM)
    """
    # This experiment must be run with a 4 VM cluster
    num_vms = len(get_faasm_worker_ips())
    assert num_vms == EXPECTED_NUM_VMS, "Expected {} VMs got: {}!".format(
        EXPECTED_NUM_VMS, num_vms
    )

    # First, work out the number of processes to run with
    if num_procs is not None:
        num_procs = [int(num_procs)]
    else:
        num_procs = MPI_KERNELS_EXPERIMENT_NPROCS

    if kernel:
        if kernel == "all":
            kernels = MPI_KERNELS_FAASM_FUNCS
        else:
            kernels = [kernel]
    else:
        kernels = MPI_KERNELS_FAASM_FUNCS

    for ind_kernel, kernel in enumerate(kernels):
        csv_name = "kernels_granny_{}.csv".format(kernel)
        _init_csv_file(csv_name)

        # Flush the cluster fist
        reset_planner(num_vms)

        for run_num in range(repeats):
            for ind_np, np in enumerate(num_procs):
                try:
                    cmdline = get_kernels_cmdline(kernel, np)
                except RuntimeError as e:
                    if kernel == "sparse":
                        print("Skipping sparse kernel for np: {}".format(np))
                        continue
                    elif kernel == "transpose":
                        print(
                            "Skipping transpose kernel for np: {}".format(np)
                        )
                        continue
                    raise e
                print_exp_status(
                    "Granny",
                    kernel,
                    np,
                    ind_kernel,
                    len(kernels),
                    ind_np,
                    len(num_procs),
                    run_num,
                    repeats,
                )

                user = MPI_KERNELS_FAASM_USER
                func = kernel
                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                    "mpi": True,
                    "mpi_world_size": np,
                }
                result_json = post_async_msg_and_get_result_json(msg)
                actual_time = get_faasm_exec_time_from_json(
                    result_json, check=True
                )
                _write_csv_line(csv_name, np, run_num, actual_time)


@task
def native(ctx, repeats=1, num_procs=None, kernel=None):
    """
    Run Kernels benchmark with OpenMPI
    """
    # First, work out the number of processes to run with
    if num_procs is not None:
        num_procs = [int(num_procs)]
    else:
        num_procs = MPI_KERNELS_EXPERIMENT_NPROCS

    if kernel:
        if kernel == "all":
            kernels = MPI_KERNELS_FAASM_FUNCS
        else:
            kernels = [kernel]
    else:
        kernels = MPI_KERNELS_FAASM_FUNCS

    # Pick one VM in the cluster at random to run native OpenMP in
    vm_names, vm_ips = get_native_mpi_pods("kernels")
    master_vm = vm_names[0]

    for ind_kernel, kernel in enumerate(kernels):
        csv_name = "kernels_native_{}.csv".format(kernel)
        _init_csv_file(csv_name)
        binary = join(KERNELS_NATIVE_DIR, "mpi_{}.o".format(kernel))

        for run_num in range(repeats):
            for ind_np, np in enumerate(num_procs):
                try:
                    cmdline = get_kernels_cmdline(kernel, np)
                except RuntimeError as e:
                    if kernel == "sparse":
                        print("Skipping sparse kernel for np: {}".format(np))
                        continue
                    elif kernel == "transpose":
                        print(
                            "Skipping transpose kernel for np: {}".format(np)
                        )
                        continue
                    raise e
                print_exp_status(
                    "OpenMPI",
                    kernel,
                    np,
                    ind_kernel,
                    len(kernels),
                    ind_np,
                    len(num_procs),
                    run_num,
                    repeats,
                )

                # Work out an allocation list to avoid having to copy hostfiles
                host_list = []
                num_cpus_per_vm = 8
                for i in range(int(np / num_cpus_per_vm)):
                    host_list += [vm_ips[i]] * num_cpus_per_vm
                if len(host_list) != np:
                    host_list += [vm_ips[int(np / num_cpus_per_vm)]] * (
                        np % num_cpus_per_vm
                    )
                assert (
                    len(host_list) == np
                ), "Host list different to num procs! ({} != {})".format(
                    len(host_list), np
                )

                mpirun_cmd = [
                    "mpirun",
                    "-np {}".format(np),
                    "-host {}".format(",".join(host_list)),
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
                run_kubectl_cmd("kernels", exec_cmd)
                actual_time = time() - start_ts
                _write_csv_line(csv_name, np, run_num, actual_time)
