from invoke import task
from os.path import join
from tasks.makespan.data import ExecutedTaskInfo
from tasks.makespan.scheduler import (
    BatchScheduler,
    WORKLOAD_ALLOWLIST,
)
from tasks.makespan.trace import load_task_trace_from_file
from tasks.makespan.util import (
    EXEC_TASK_INFO_FILE_PREFIX,
    IDLE_CORES_FILE_PREFIX,
    init_csv_file,
    get_idle_core_count_from_task_info,
    write_line_to_csv,
)
from tasks.util.env import RESULTS_DIR
from typing import Dict


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
    """
    Run: `inv makespan.run --num-vms <> --workload <> --backend <> --trace <>`
    """
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
    if workload == "all":
        workload = WORKLOAD_ALLOWLIST
    elif workload in WORKLOAD_ALLOWLIST:
        workload = [workload]
    else:
        print("Workload must be one in: {}".format(WORKLOAD_ALLOWLIST))
        raise RuntimeError("Unrecognised workload type: {}".format(workload))

    for wload in workload:
        # IMPORTANT: here we use that the smallest job size `min_job_size` is
        # half a VM, and that all jobs size have `min_job_size | job_size`
        if wload == "pc-opt":
            scheduler = BatchScheduler(
                backend,
                wload,
                num_vms * 2,
                num_tasks,
                int(num_cores_per_vm / 2),
                num_users,
            )
        else:
            scheduler = BatchScheduler(
                backend, wload, num_vms, num_tasks, num_cores_per_vm, num_users
            )

        init_csv_file(
            wload, backend, num_vms, num_tasks, num_cores_per_vm, num_users
        )

        task_trace = load_task_trace_from_file(
            num_tasks, num_cores_per_vm, num_users
        )

        executed_task_info = scheduler.run(backend, wload, task_trace)

        num_idle_cores_per_time_step = get_idle_core_count_from_task_info(
            executed_task_info, task_trace, num_vms, num_cores_per_vm
        )
        for time_step in num_idle_cores_per_time_step:
            write_line_to_csv(
                wload,
                backend,
                IDLE_CORES_FILE_PREFIX,
                num_vms,
                num_tasks,
                num_cores_per_vm,
                num_users,
                time_step,
                num_idle_cores_per_time_step[time_step],
            )

        # Finally shutdown the scheduler
        scheduler.shutdown()


@task()
def idle_cores_from_exec_task(
    ctx,
    num_vms=4,
    workload="uc-opt",
    backend="compose",
    trace=None,
    num_tasks=100,
    num_cores_per_vm=4,
    num_users=2,
):
    result_dir = join(RESULTS_DIR, "makespan")
    executed_task_info: Dict[int, ExecutedTaskInfo] = {}
    # Get executed task info from file
    csv_name = "makespan_{}_{}_{}_{}_{}_{}_{}.csv".format(
        EXEC_TASK_INFO_FILE_PREFIX,
        workload,
        backend,
        num_vms,
        num_tasks,
        num_cores_per_vm,
        num_users,
    )
    csv_file = join(result_dir, csv_name)
    with open(csv_file, "r") as in_file:
        for line in in_file:
            if "TaskId" in line:
                continue
            line = line.strip()
            task_id = int(line.split(",")[0])
            time_executing = int(line.split(",")[1])
            time_in_queue = int(line.split(",")[2])
            exec_start_ts = float(line.split(",")[3])
            exec_end_ts = float(line.split(",")[4])
            executed_task_info[task_id] = ExecutedTaskInfo(
                task_id,
                time_executing,
                time_in_queue,
                exec_start_ts,
                exec_end_ts,
            )

    task_trace = load_task_trace_from_file(
        num_tasks, num_cores_per_vm, num_users
    )
    num_idle_cores_per_time_step = get_idle_core_count_from_task_info(
        executed_task_info, task_trace, num_vms, num_cores_per_vm
    )
    print(num_idle_cores_per_time_step)
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
