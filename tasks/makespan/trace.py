from random import uniform
from tasks.makespan.scheduler import TaskObject
from typing import List


def generate_task_trace(
    num_tasks: int, num_cores_per_vm: int
) -> List[TaskObject]:
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
    for idx in range(num_tasks):
        ws_idx = int(uniform(0, num_pos_ws))
        wl_idx = int(uniform(0, num_pos_wl))
        task_trace.append(
            TaskObject(
                idx, possible_workloads[wl_idx], possible_world_sizes[ws_idx]
            )
        )

    return task_trace
