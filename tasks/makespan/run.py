from invoke import task
from tasks.makespan.scheduler import BatchScheduler, WORKLOAD_ALLOWLIST
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
    num_vms,
    num_cores_per_vm,
    workload,
    num_tasks=None,
    enable_migration=False,
):
    num_vms = int(num_vms)
    num_cores_per_vm = int(num_cores_per_vm)
    if not num_tasks:
        num_tasks = [10, 20, 30, 40, 50, 60, 70]
    else:
        num_tasks = [int(num_tasks)]

    # Choose workloads: "native", "wasm", "batch", or "all"
    if workload not in WORKLOAD_ALLOWLIST:
        print("Workload must be one in: 'native', 'wasm' or 'batch'")
        raise RuntimeError("Unrecognised workload type: {}".format(workload))

    # Initialise batch scheduler
    scheduler = BatchScheduler(
        workload, num_vms, num_cores_per_vm, enable_migration
    )

    for ntask in num_tasks:

        # Use one file for num tasks and workload for reliabaility
        init_csv_file(workload, ntask)

        task_trace = load_task_trace_from_file(ntask)

        makespan_start_time = time.time()
        exec_info = scheduler.run(workload, task_trace)
        makespan_time = int(time.time() - makespan_start_time)
        write_line_to_csv(
            workload, ntask, MAKESPAN_FILE_PREFIX, ntask, makespan_time
        )

        for key in exec_info:
            print(exec_info[key])

    # Finally shutdown the scheduler
    scheduler.shutdown()
