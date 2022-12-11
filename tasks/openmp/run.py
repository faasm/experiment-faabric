from invoke import task
from json import loads as json_loads
from os import makedirs
from os.path import join
from pprint import pprint
from requests import post
from time import sleep, time
from tasks.util.env import (
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    get_faasm_invoke_host_port,
)

# TODO: move this to tasks.openmp.env
from tasks.makespan.env import (
    DGEMM_DOCKER_BINARY,
    DGEMM_FAASM_USER,
    DGEMM_FAASM_FUNC,
    LULESH_FAASM_USER,
    LULESH_FAASM_FUNC,
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
def granny(ctx, workload="dgemm", num_threads=None, repeats=5):
    if num_threads is not None:
        num_threads = [num_threads]
    else:
        num_threads = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16]

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

    # Flush the cluster first
    print("Flushing functions, state, and shared files from workers")
    msg = {"type": MESSAGE_TYPE_FLUSH}
    print("Posting to {} msg:".format(url))
    pprint(msg)
    response = post(url, json=msg, timeout=None)
    if response.status_code != 200:
        print(
            "Flush request failed: {}:\n{}".format(
                response.status_code, response.text
            )
        )
    print("Waiting for flush to propagate...")
    sleep(5)
    print("Done waiting")

    for wload in workload:
        csv_name = "openmp_{}_granny.csv".format(workload)
        _init_csv_file(csv_name)
        for r in range(int(repeats)):
            for nthread in num_threads:

                if wload == "dgemm":
                    user = DGEMM_FAASM_USER
                    func = DGEMM_FAASM_FUNC
                    # cmdline = get_dgemm_cmdline(nthread)
                    cmdline = get_dgemm_cmdline(nthread, iterations=20)
                else:
                    user = LULESH_FAASM_USER
                    func = LULESH_FAASM_FUNC
                    cmdline = get_lulesh_cmdline(nthread)
                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                    "async": True,
                }
                print("Posting to {} msg:".format(url))
                pprint(msg)
                # Post asynch request
                response = post(url, json=msg, timeout=None)

                # Get the async message id
                if response.status_code != 200:
                    print(
                        "Initial request failed: {}:\n{}".format(
                            response.status_code, response.text
                        )
                    )
                print("Response: {}".format(response.text))
                msg_id = int(response.text.strip())

                # Start polling for the result
                print("Polling message {}".format(msg_id))
                while True:
                    interval = 2
                    sleep(interval)

                    status_msg = {
                        "user": user,
                        "function": func,
                        "status": True,
                        "id": msg_id,
                    }
                    response = post(url, json=status_msg)

                    if not response.text or response.text.startswith("FAILED"):
                        raise RuntimeError("Error running task!")
                    elif response.text.startswith("RUNNING"):
                        continue
                    elif not response.text:
                        raise RuntimeError("Empty status response")

                    # If we reach this point it means the call has succeeded
                    result_json = json_loads(response.text, strict=False)
                    actual_time = int(
                        get_faasm_exec_time_from_json(result_json)
                    )
                    _write_csv_line(csv_name, nthread, r, actual_time)
                    break
                print("Actual time for msg {}: {}".format(msg_id, actual_time))


@task
def native(ctx, workload="dgemm", num_threads=None, repeats=5, ctrs_per_vm=1):
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
                openmp_cmd = "bash -c '{} {}'".format(
                    DGEMM_DOCKER_BINARY,
                    get_dgemm_cmdline(nthread, iterations=20),
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
