from faasmctl.util.flush import flush_workers
from invoke import task
from os import makedirs
from os.path import basename, join
from tasks.util.env import (
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from tasks.util.env import (
    LAMMPS_DOCKER_BINARY,
    LAMMPS_DOCKER_DIR,
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_FUNC,
)
from time import time

# TODO: move this elsewhere
from tasks.lammps.env import get_faasm_benchmark
from tasks.util.openmpi import (
    get_native_mpi_pods,
    run_kubectl_cmd,
)

MESSAGE_TYPE_FLUSH = 3


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "mpi")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("NumProc,Run,ExecTimeSecs\n")


def _write_csv_line(csv_name, num_threads, run, exec_time):
    result_dir = join(RESULTS_DIR, "mpi")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{}\n".format(num_threads, run, exec_time))


@task
def granny(ctx, workload="compute", num_procs=None, repeats=5):
    """
    Run a LAMMPS simulation with Granny
    """
    if num_procs is not None:
        num_procs = [num_procs]
    else:
        num_procs = [2, 4, 6, 8, 10, 12, 14, 16]

    all_workloads = ["compute", "network", "all"]
    if workload not in all_workloads:
        raise RuntimeError(
            "Unrecognised workload ({}) must be one in: {}".format(
                workload, all_workloads
            )
        )
    elif workload == "all":
        workload = all_workloads[:-1]
    else:
        workload = [workload]

    # Flush the cluster first
    flush_workers()

    for wload in workload:
        csv_name = "mpi_lammps_{}_granny.csv".format(wload)
        _init_csv_file(csv_name)
        file_name = basename(get_faasm_benchmark(wload)["data"][0])
        user = LAMMPS_FAASM_USER
        func = LAMMPS_FAASM_FUNC
        cmdline = "-in faasm://lammps-data/{}".format(file_name)
        for r in range(int(repeats)):
            for nproc in num_procs:
                msg = {
                    "user": user,
                    "function": func,
                    "cmdline": cmdline,
                    "mpi": True,
                    "mpi_world_size": nproc,
                    "async": True,
                }
                result_json = post_async_msg_and_get_result_json(msg)
                actual_time = get_faasm_exec_time_from_json(result_json)
                _write_csv_line(csv_name, nproc, r, actual_time)


@task
def native(ctx, workload="compute", num_procs=None, repeats=5, ctrs_per_vm=1):
    """
    Run a LAMMPS simulation with OpenMPI
    """
    if num_procs is not None:
        num_procs = [num_procs]
    else:
        num_procs = [2, 4, 6, 8, 10, 12, 14, 16]

    all_workloads = ["compute", "network", "all"]
    if workload not in all_workloads:
        raise RuntimeError(
            "Unrecognised workload ({}) must be one in: {}".format(
                workload, all_workloads
            )
        )
    elif workload == "all":
        workload = all_workloads[:-1]
    else:
        workload = [workload]

    # Pick one VM in the cluster at random to run native OpenMP in
    vm_names, vm_ips = get_native_mpi_pods("makespan")
    master_vm = vm_names[0]
    master_ip = vm_ips[0]
    worker_ip = vm_ips[1]

    for wload in workload:
        csv_name = "mpi_lammps_{}_native-{}.csv".format(wload, ctrs_per_vm)
        _init_csv_file(csv_name)
        binary = LAMMPS_DOCKER_BINARY
        lammps_dir = LAMMPS_DOCKER_DIR
        data_file = get_faasm_benchmark(wload)["data"][0]
        native_cmdline = "-in {}/{}.faasm.native".format(lammps_dir, data_file)
        for r in range(int(repeats)):
            for nproc in num_procs:
                # Work out an allocation list to avoid having to copy hostfiles
                num_cores_per_ctr = 8
                allocated_pod_ips = []
                if nproc > num_cores_per_ctr:
                    allocated_pod_ips = [
                        "{}:{}".format(master_ip, num_cores_per_ctr),
                        "{}:{}".format(worker_ip, nproc - num_cores_per_ctr),
                    ]
                else:
                    allocated_pod_ips = ["{}:{}".format(master_ip, nproc)]

                mpirun_cmd = [
                    "mpirun",
                    "-np {}".format(nproc),
                    "-host {}".format(",".join(allocated_pod_ips)),
                    binary,
                    native_cmdline,
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
                _write_csv_line(csv_name, nproc, r, actual_time)
                print("Actual time: {}".format(actual_time))
