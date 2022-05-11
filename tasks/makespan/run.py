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
def run(ctx, num_vms, num_cores_per_vm, workload="all"):
    num_vms = int(num_vms)
    num_cores_per_vm = int(num_cores_per_vm)
    num_tasks = [10, 15, 20]
    # num_tasks = [50, 100, 150]

    # Choose workloads: "native", "wasm", "batch", or "all"
    if workload == "all":
        workloads = WORKLOAD_ALLOWLIST
    elif workload in WORKLOAD_ALLOWLIST:
        workloads = [workload]
    else:
        print("Workload must be one in: 'native', 'wasm', 'batch' or 'all'")
        raise RuntimeError("Unrecognised workload type: {}".format(workload))

    for wl in workloads:
        init_csv_file(wl)

    # Initialise batch scheduler
    scheduler = BatchScheduler(num_vms, num_cores_per_vm)

    for ntask in num_tasks:
        task_trace = load_task_trace_from_file(ntask)

        for wl in workloads:
            makespan_start_time = time.time()
            exec_info = scheduler.run(wl, task_trace)
            makespan_time = int(time.time() - makespan_start_time)
            write_line_to_csv(wl, MAKESPAN_FILE_PREFIX, ntask, makespan_time)

            for key in exec_info:
                print(exec_info[key])

    # Finally shutdown the scheduler
    scheduler.shutdown()
