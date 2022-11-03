from os import makedirs
from os.path import join
from tasks.util.env import (
    RESULTS_DIR,
)

IDLE_CORES_FILE_PREFIX = "idle-cores"


def init_csv_file(workload, num_vms, num_tasks, num_cores_per_vm, num_users):
    result_dir = join(RESULTS_DIR, "makespan")
    makedirs(result_dir, exist_ok=True)

    csv_name_ic = "makespan_{}_{}_{}_{}_{}_{}.csv".format(
        IDLE_CORES_FILE_PREFIX,
        workload,
        num_vms,
        num_tasks,
        num_cores_per_vm,
        num_users,
    )

    makedirs(RESULTS_DIR, exist_ok=True)
    ic_file = join(result_dir, csv_name_ic)
    with open(ic_file, "w") as out_file:
        out_file.write("TimeStampSecs,NumIdleCores\n")


def write_line_to_csv(
    workload, exp_key, num_vms, num_tasks, num_cores_per_vm, num_users, *args
):
    result_dir = join(RESULTS_DIR, "makespan")
    if exp_key == IDLE_CORES_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}_{}_{}.csv".format(
            IDLE_CORES_FILE_PREFIX,
            workload,
            num_vms,
            num_tasks,
            num_cores_per_vm,
            num_users,
        )
        makespan_file = join(result_dir, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{}\n".format(*args))
