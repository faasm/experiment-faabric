from faasmctl.util.config import get_faasm_worker_ips
from faasmctl.util.planner import reset as reset_planner
from invoke import task
from os import makedirs
from os.path import basename, join
from tasks.migration.util import generate_host_list
from tasks.util.env import RESULTS_DIR
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from tasks.util.lammps import (
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_MIGRATION_NET_FUNC,
    LAMMPS_SIM_WORKLOAD,
    LAMMPS_SIM_WORKLOAD_CONFIGS,
    get_faasm_benchmark,
    get_lammps_migration_params,
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


@task(default=True, iterable=["w"])
def run(ctx, w, check_in=None, repeats=1, num_cores_per_vm=8):
    """
    Run migration experiment
    """
    num_vms = len(get_faasm_worker_ips())
    assert num_vms == 2, "Expected 2 VMs got: {}!".format(num_vms)
    # data_file = basename(get_faasm_benchmark(LAMMPS_SIM_WORKLOAD)["data"][0])
    # TODO: is this a good idea? FIXME FIXME DELETE ME
    data_file = basename(get_faasm_benchmark("compute")["data"][0])

    if check_in is None:
        check_array = [0, 2, 4, 6, 8, 10]
    else:
        check_array = [int(check_in)]

    for workload in w:
        if workload not in LAMMPS_SIM_WORKLOAD_CONFIGS:
            print(
                "Unrecognised workload config ({}) must be one in: {}".format(
                    workload, LAMMPS_SIM_WORKLOAD.keys()
                )
            )
        workload_config = LAMMPS_SIM_WORKLOAD_CONFIGS[workload]

        csv_name = "migration_{}.csv".format(workload)
        _init_csv_file(csv_name)

        for check in check_array:
            for run_num in range(repeats):
                reset_planner(num_vms)

                # Print progress
                print(
                    "Running migration micro-benchmark (wload:"
                    + "{} - check-at: {} - repeat: {}/{})".format(
                        workload, check, run_num + 1, repeats
                    )
                )

                """
                TODO: do we want to keep the all-to-all baseline?
                if workload == "all-to-all":
                    num_loops = 100000
                    user = MPI_MIGRATE_FAASM_USER
                    func = MPI_MIGRATE_FAASM_FUNC
                    cmdline = "{} {}".format(
                        check if check != 0 else 5, num_loops
                    )
                """

                # Run LAMMPS
                cmdline = "-in faasm://lammps-data/{}".format(data_file)
                msg = {
                    "user": LAMMPS_FAASM_USER,
                    "function": LAMMPS_FAASM_MIGRATION_NET_FUNC,
                    "cmdline": cmdline,
                    "mpi_world_size": int(num_cores_per_vm),
                    "input_data": get_lammps_migration_params(
                        num_loops=5,
                        num_net_loops=workload_config["num_net_loops"],
                        chunk_size=workload_config["chunk_size"],
                    ),
                }

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

                # Invoke with or without pre-loading
                result_json = post_async_msg_and_get_result_json(
                    msg, host_list=host_list
                )
                actual_time = get_faasm_exec_time_from_json(result_json)
                _write_csv_line(
                    csv_name, num_cores_per_vm, check, run_num, actual_time
                )

                sleep(2)
