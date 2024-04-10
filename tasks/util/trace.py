from os import makedirs
from os.path import join
from tasks.makespan.data import TaskObject
from tasks.util.env import PROJ_ROOT

MAKESPAN_TRACES_DIR = join(PROJ_ROOT, "tasks", "makespan", "traces")

def dump_task_trace_to_file(task_trace, workload, num_tasks, num_cores_per_vm):
    makedirs(MAKESPAN_TRACES_DIR, exist_ok=True)
    file_name = "trace_{}_{}_{}.csv".format(
        workload, num_tasks, num_cores_per_vm
    )
    task_file = join(MAKESPAN_TRACES_DIR, file_name)
    with open(task_file, "w") as out_file:
        out_file.write("TaskId,App,Size,InterArrivalTimeSecs\n")
        for t in task_trace:
            out_file.write(
                "{},{},{},{}\n".format(
                    t.task_id, t.app, t.size, t.inter_arrival_time
                )
            )
    print(
        "Written trace with {} tasks to {}".format(len(task_trace), task_file)
    )


def load_task_trace_from_file(workload, num_tasks, num_cores_per_vm):
    file_name = "trace_{}_{}_{}.csv".format(
        workload, num_tasks, num_cores_per_vm
    )
    task_file = join(MAKESPAN_TRACES_DIR, file_name)
    task_trace = []
    with open(task_file, "r") as in_file:
        for line in in_file:
            if "TaskId" in line:
                continue
            if len(task_trace) == num_tasks:
                break
            tokens = line.rstrip().split(",")
            task_trace.append(
                TaskObject(
                    int(tokens[0]),
                    tokens[1],
                    int(tokens[2]),
                    int(tokens[3]),
                )
            )
    return task_trace
