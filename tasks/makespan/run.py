from invoke import task
from tasks.makespan.scheduler import (
    BatchScheduler,
    NATIVE_WORKLOADS,
    WORKLOAD_ALLOWLIST,
)
from tasks.makespan.trace import load_task_trace_from_file
from tasks.makespan.util import (
    init_csv_file,
    write_line_to_csv,
    MAKESPAN_FILE_PREFIX,
)
import time


@task(default=True)
def run(
    ctx,
    num_vms=4,
    workload="uc-opt",
    backend="compose",
    trace=None,
    num_tasks=10,
    num_cores_per_vm=4,
    num_users=2,
):
    num_vms = int(num_vms)

    # If a trace file is specified, it takes preference over the other values
    if trace is not None:
        num_tasks = trace.split("_")[1]
        num_cores_per_vm = trace.split("_")[2]
        num_users = trace.split("_")[3][:-4]

    # Choose workloads: "pc-opt", "uc-opt", "st-opt", or "granny"
    if workload not in WORKLOAD_ALLOWLIST:
        print("Workload must be one in: {}".format(WORKLOAD_ALLOWLIST))
        raise RuntimeError("Unrecognised workload type: {}".format(workload))

    scheduler = BatchScheduler(workload, num_vms, num_cores_per_vm, num_users)

    init_csv_file(workload, num_vms, num_tasks, num_cores_per_vm, num_users)

    task_trace = load_task_trace_from_file(
        num_tasks, num_cores_per_vm, num_users
    )

    exec_info = scheduler.run(workload, task_trace)

    for key in exec_info:
        print(exec_info[key])

    # Finally shutdown the scheduler
    scheduler.shutdown()
