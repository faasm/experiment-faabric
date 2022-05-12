from invoke import task
from os import makedirs
from os.path import join
from random import uniform
from tasks.makespan.scheduler import TaskObject
from tasks.util.env import PROJ_ROOT
from typing import List

MAKESPAN_TRACES_DIR = join(PROJ_ROOT, "tasks", "makespan", "traces")


def dump_task_trace_to_file(task_trace):
    makedirs(MAKESPAN_TRACES_DIR, exist_ok=True)
    file_name = "trace_{}.csv".format(len(task_trace))
    task_file = join(MAKESPAN_TRACES_DIR, file_name)
    with open(task_file, "w") as out_file:
        for t in task_trace:
            out_file.write("{},{},{}\n".format(t.task_id, t.app, t.world_size))
    print(
        "Written trace with {} tasks to {}".format(len(task_trace), task_file)
    )


def load_task_trace_from_file(num_tasks):
    file_name = "trace_100.csv"
    task_file = join(MAKESPAN_TRACES_DIR, file_name)
    task_trace = []
    with open(task_file, "r") as in_file:
        for line in in_file:
            if len(task_trace) == num_tasks:
                break
            tokens = line.rstrip().split(",")
            task_trace.append(
                TaskObject(int(tokens[0]), tokens[1], int(tokens[2]))
            )
    print(
        "Loaded task trace with {} tasks from {}".format(
            len(task_trace), task_file
        )
    )
    return task_trace


@task(iterable=["num_tasks"])
def generate_task_trace(ctx, num_cores_per_vm, num_tasks):
    for nt in num_tasks:
        nt = int(nt)
        num_cores_per_vm = int(num_cores_per_vm)
        possible_world_sizes = [
            int(num_cores_per_vm / 2),
            int(num_cores_per_vm),
            int(num_cores_per_vm * 1.5),
            int(num_cores_per_vm * 2),
        ]
        possible_workloads = ["network", "compute"]

        # Generate the random task trace
        task_trace: List[TaskObject] = []
        num_pos_ws = len(possible_world_sizes)
        num_pos_wl = len(possible_workloads)
        for idx in range(nt):
            ws_idx = int(uniform(0, num_pos_ws))
            wl_idx = int(uniform(0, num_pos_wl))
            task_trace.append(
                TaskObject(
                    idx,
                    possible_workloads[wl_idx],
                    possible_world_sizes[ws_idx],
                )
            )

        dump_task_trace_to_file(task_trace)
