from os import makedirs
from os.path import join
from tasks.util.env import (
    RESULTS_DIR,
)

TIQ_FILE_PREFIX = "tiq"
MAKESPAN_FILE_PREFIX = "makespan"


def init_csv_file(workload, num_tasks):
    result_dir = join(RESULTS_DIR, "makespan")
    makedirs(result_dir, exist_ok=True)

    csv_name_makespan = "makespan_{}_{}_time.csv".format(workload, num_tasks)
    csv_name_tiq = "makespan_{}_{}_time_in_queue.csv".format(
        workload, num_tasks
    )

    makedirs(RESULTS_DIR, exist_ok=True)
    makespan_file = join(result_dir, csv_name_makespan)
    with open(makespan_file, "w") as out_file:
        out_file.write("NumTasks,Makespan\n")
    tiq_file = join(result_dir, csv_name_tiq)
    with open(tiq_file, "w") as out_file:
        out_file.write("NumTasks,TaskId,TimeInQueue,ExecTime,TimeSinceStart\n")


def write_line_to_csv(workload, num_tasks, file_name, *args):
    result_dir = join(RESULTS_DIR, "makespan")

    if file_name == "makespan":
        csv_name = "makespan_{}_{}_time.csv".format(workload, num_tasks)
        makespan_file = join(result_dir, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{}\n".format(*args))
    elif file_name == "tiq":
        csv_name = "makespan_{}_{}_time_in_queue.csv".format(
            workload, num_tasks
        )
        makespan_file = join(result_dir, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{},{},{},{}\n".format(*args))
    else:
        raise RuntimeError("Unrecognised file name: {}".format(file_name))
