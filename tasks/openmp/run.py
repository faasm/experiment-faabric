from invoke import task
from os import makedirs
from os.path import join
from tasks.util.env import (
    DGEMM_DOCKER_BINARY,
    DGEMM_FAASM_USER,
    DGEMM_FAASM_FUNC,
    LULESH_DOCKER_BINARY,
    LULESH_FAASM_USER,
    LULESH_FAASM_FUNC,
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    get_faasm_invoke_host_port,
    flush_hosts,
    post_async_msg_and_get_result_json,
)
from time import time

# TODO: move this to tasks.openmp.env
from tasks.makespan.env import (
    get_dgemm_cmdline,
    get_lulesh_cmdline,
)
from tasks.util.openmpi import (
    get_native_mpi_pods,
    run_kubectl_cmd,
)

MESSAGE_TYPE_FLUSH = 3


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


@task
def granny(ctx, workload="dgemm", num_threads=None, repeats=1):
    if num_threads is not None:
        num_threads = [num_threads]
    else:
        # num_threads = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16]
        # num_threads = [1, 2, 3, 4, 5, 6, 7, 8]
        num_threads = [7, 8]

    all_workloads = ["dgemm", "lulesh", "all"]
    if workload not in all_workloads:
        raise RuntimeError(
            "Unrecognised workload ({}) must be one in: {}".format(
                workload, all_workloads
            )
        )
    elif workload == "all":
        workload = ["dgemm", "lulesh"]
    else:
        workload = [workload]

    host, port = get_faasm_invoke_host_port()
    url = "http://{}:{}".format(host, port)

    for wload in workload:
        csv_name = "openmp_{}_granny.csv".format(wload)
        _init_csv_file(csv_name)
        for r in range(int(repeats)):
            for nthread in num_threads:

                flush_hosts()

                if wload == "dgemm":
                    user = DGEMM_FAASM_USER
                    func = DGEMM_FAASM_FUNC
                    cmdline = get_dgemm_cmdline(nthread, iterations=20)
                else:
                    user = LULESH_FAASM_USER
                    func = LULESH_FAASM_FUNC
                    cmdline = get_lulesh_cmdline()
                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                    "async": True,
                }
                if wload == "lulesh":
                    msg["input_data"] = str(nthread)

                result_json = post_async_msg_and_get_result_json(msg, url)
                actual_time = int(
                    get_faasm_exec_time_from_json(result_json)
                )
                _write_csv_line(csv_name, nthread, r, actual_time)
                print("Actual time: {}".format(actual_time))


@task
def native(ctx, workload="dgemm", num_threads=None, repeats=1, ctrs_per_vm=1):
    if num_threads is not None:
        num_threads = [num_threads]
    else:
        num_threads = [1, 2, 3, 4, 5, 6, 7, 8]

    all_workloads = ["dgemm", "lulesh", "all"]
    if workload not in all_workloads:
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
    vm_names, vm_ips = get_native_mpi_pods("makespan")
    master_vm = vm_names[0]

    for wload in workload:
        csv_name = "openmp_{}_native-{}.csv".format(wload, ctrs_per_vm)
        _init_csv_file(csv_name)
        for r in range(int(repeats)):
            for nthread in num_threads:
                if wload == "dgemm":
                    binary = DGEMM_DOCKER_BINARY,
                    cmdline = get_dgemm_cmdline(nthread, iterations=20)
                else:
                    binary = LULESH_DOCKER_BINARY
                    cmdline = get_lulesh_cmdline()
                openmp_cmd = "bash -c 'OPENMP_NUM_THREADS={} {} {}'".format(
                    nthread,
                    binary,
                    cmdline
                )

                exec_cmd = [
                    "exec",
                    master_vm,
                    "--",
                    openmp_cmd,
                ]
                exec_cmd = " ".join(exec_cmd)

                start_ts = time()
                run_kubectl_cmd("makespan", exec_cmd)
                actual_time = int(time() - start_ts)
                _write_csv_line(csv_name, nthread, r, actual_time)
                print("Actual time: {}".format(actual_time))
