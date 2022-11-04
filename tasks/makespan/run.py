from invoke import task
from tasks.makespan.scheduler import (
    BatchScheduler,
    WORKLOAD_ALLOWLIST,
)
from tasks.makespan.trace import load_task_trace_from_file
from tasks.makespan.util import (
    IDLE_CORES_FILE_PREFIX,
    init_csv_file,
    get_idle_core_count_from_task_info,
    write_line_to_csv,
)


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
        num_tasks = int(trace.split("_")[1])
        num_cores_per_vm = int(trace.split("_")[2])
        num_users = int(trace.split("_")[3][:-4])
    else:
        num_tasks = int(num_tasks)
        num_cores_per_vm = int(num_cores_per_vm)
        num_users = int(num_users)

    # Choose workloads: "pc-opt", "uc-opt", "st-opt", or "granny"
    if workload not in WORKLOAD_ALLOWLIST:
        print("Workload must be one in: {}".format(WORKLOAD_ALLOWLIST))
        raise RuntimeError("Unrecognised workload type: {}".format(workload))

    scheduler = BatchScheduler(
        backend, workload, num_vms, num_tasks, num_cores_per_vm, num_users
    )

    init_csv_file(
        workload, backend, num_vms, num_tasks, num_cores_per_vm, num_users
    )

    task_trace = load_task_trace_from_file(
        num_tasks, num_cores_per_vm, num_users
    )

    executed_task_info = scheduler.run(backend, workload, task_trace)

    """
    num_idle_cores_per_time_step = get_idle_core_count_from_task_info(
        executed_task_info, task_trace, num_vms, num_cores_per_vm
    )
    for time_step in num_idle_cores_per_time_step:
        write_line_to_csv(
            workload,
            backend,
            IDLE_CORES_FILE_PREFIX,
            num_vms,
            num_tasks,
            num_cores_per_vm,
            num_users,
            time_step,
            num_idle_cores_per_time_step[time_step],
        )
    """

    # Finally shutdown the scheduler
    scheduler.shutdown()
