from base64 import b64encode
from faasmctl.util.config import get_faasm_worker_ips
from faasmctl.util.flush import flush_workers
from faasmctl.util.planner import reset as reset_planner
from invoke import task
from os import makedirs
from os.path import basename, join
from tasks.lammps.env import get_faasm_benchmark
from tasks.migration.util import generate_host_list
from tasks.util.env import (
    MPI_MIGRATE_FAASM_USER,
    MPI_MIGRATE_FAASM_FUNC,
    LAMMPS_MIGRATION_FAASM_USER,
    LAMMPS_MIGRATION_FAASM_FUNC,
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from time import sleep


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "migration")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("WorldSize,Check,Run,Time\n")

    return result_file


def _write_csv_line(csv_name, nprocs, check, run_num, actual_time):
    result_dir = join(RESULTS_DIR, "migration")
    result_file = join(result_dir, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write(
            "{},{},{},{:.2f}\n".format(nprocs, check, run_num, actual_time)
        )


@task(default=True)
def run(ctx, workload="all", check_in=None, repeats=1, num_cores_per_vm=8):
    """
    Run migration experiment
    """
    num_workers = len(get_faasm_worker_ips())
    reset_planner(num_workers)

    all_workloads = ["all-to-all", "lammps", "all"]
    if workload == "all":
        workload = all_workloads[:-1]
    elif workload in all_workloads:
        workload = [workload]
    else:
        raise RuntimeError(
            "Unrecognised workload: {}. Must be one in: {}".format(
                workload, all_workloads
            )
        )

    if check_in is None:
        check_array = [0, 2, 4, 6, 8, 10]
    else:
        check_array = [int(check_in)]

    for wload in workload:
        csv_name = "migration_{}.csv".format(wload)
        _init_csv_file(csv_name)

        for check in check_array:
            for run_num in range(repeats):
                # First, flush the host state
                flush_workers()
                sleep(2)

                # Print progress
                print(
                    "Running migration micro-benchmark (wload:"
                    + "{} - check-at: {} - repeat: {}/{})".format(
                        wload, check, run_num + 1, repeats
                    )
                )

                if wload == "all-to-all":
                    num_loops = 100000
                    user = MPI_MIGRATE_FAASM_USER
                    func = MPI_MIGRATE_FAASM_FUNC
                    cmdline = "{} {}".format(
                        check if check != 0 else 5, num_loops
                    )
                else:
                    file_name = basename(
                        # get_faasm_benchmark("network")["data"][0]
                        get_faasm_benchmark("compute-xl")["data"][0]
                    )
                    user = LAMMPS_MIGRATION_FAASM_USER
                    func = LAMMPS_MIGRATION_FAASM_FUNC
                    cmdline = "-in faasm://lammps-data/{}".format(file_name)
                    num_loops = 5
                    check_at_loop = num_loops if check == 0 else check / 2
                    input_data = "{} {}".format(check_at_loop, num_loops)

                if check == 0:
                    # Setting a check fraction of 0 means we don't
                    # under-schedule. We use it as a baseline
                    host_list = None
                else:
                    # Setting a check period different than 0 means that we
                    # want to under-schedule and create a migration opportunity
                    # We do so by pre-loading a scheduling decision to the
                    # planner
                    host_list = generate_host_list([num_cores_per_vm / 2] * 2)

                msg = {
                    "user": user,
                    "function": func,
                    "mpi": True,
                    "mpi_world_size": int(num_cores_per_vm),
                    "cmdline": cmdline,
                }
                if wload == "lammps":
                    msg["input_data"] = b64encode(
                        input_data.encode("utf-8")
                    ).decode("utf-8")

                # Invoke with or without pre-loading
                result_json = post_async_msg_and_get_result_json(
                    msg, host_list=host_list
                )
                actual_time = get_faasm_exec_time_from_json(result_json)
                _write_csv_line(
                    csv_name, num_cores_per_vm, check, run_num, actual_time
                )
