from invoke import task
from os.path import join
from tasks.makespan.data import ExecutedTaskInfo
from tasks.makespan.scheduler import (
    BatchScheduler,
)
from tasks.makespan.trace import load_task_trace_from_file
from tasks.makespan.util import (
    EXEC_TASK_INFO_FILE_PREFIX,
    IDLE_CORES_FILE_PREFIX,
    init_csv_file,
    get_idle_core_count_from_task_info,
    get_num_cores_from_trace,
    get_num_tasks_from_trace,
    get_workload_from_trace,
    write_line_to_csv,
)
from tasks.util.env import RESULTS_DIR
from typing import Dict


@task(default=True)
def run(
    ctx,
    backend="compose",
    num_vms=4,
    ctrs_per_vm=1,
    granny=False,
    trace=None,
):
    """
    Run: `inv makespan.run --backend <> --num-vms <> --ctrs-per-vm <>
        --trace <> [--granny]`
    """
    num_vms = int(num_vms)
    ctrs_per_vm = int(ctrs_per_vm)

    # If a trace file is specified, it takes preference over the other values
    if trace is not None:
        job_workload = get_workload_from_trace(trace)
        num_tasks = get_num_tasks_from_trace(trace)
        num_cores_per_vm = get_num_cores_from_trace(trace)
    else:
        raise RuntimeError("Must provide a trace file name")

    if granny:
        workload = "granny"
        num_ctrs = num_vms
        num_cores_per_ctr = num_cores_per_vm
    else:
        workload = "native"
        num_ctrs = int(num_vms * ctrs_per_vm)
        num_cores_per_ctr = int(num_cores_per_vm / ctrs_per_vm)

    scheduler = BatchScheduler(
        backend,
        workload,
        num_ctrs,
        num_tasks,
        num_cores_per_ctr,
        ctrs_per_vm,
    )

    init_csv_file(
        workload,
        backend,
        num_vms,
        num_tasks,
        num_cores_per_vm,
        ctrs_per_vm,
    )

    task_trace = load_task_trace_from_file(
        job_workload, num_tasks, num_cores_per_vm
    )

    executed_task_info = scheduler.run(backend, workload, task_trace)

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
            ctrs_per_vm,
            time_step,
            num_idle_cores_per_time_step[time_step],
        )

    # Finally shutdown the scheduler
    scheduler.shutdown()


@task()
def idle_cores_from_exec_task(
    ctx,
    backend="compose",
    num_vms=4,
    ctrs_per_vm=1,
    trace=None,
    granny=False,
):
    result_dir = join(RESULTS_DIR, "makespan")
    executed_task_info: Dict[int, ExecutedTaskInfo] = {}

    num_vms = int(num_vms)

    # If a trace file is specified, it takes preference over the other values
    if trace is not None:
        job_workload = get_workload_from_trace(trace)
        num_tasks = get_num_tasks_from_trace(trace)
        num_cores_per_vm = get_num_cores_from_trace(trace)
    else:
        raise RuntimeError("Must provide a trace file name")

    if granny:
        workload = "granny"
    else:
        workload = "native-{}".format(ctrs_per_vm)

    # Get executed task info from file
    csv_name = "makespan_{}_{}_{}_{}_{}_{}.csv".format(
        EXEC_TASK_INFO_FILE_PREFIX,
        workload,
        backend,
        num_vms,
        num_tasks,
        num_cores_per_vm,
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
        job_workload, num_tasks, num_cores_per_vm
    )
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
            ctrs_per_vm,
            time_step,
            num_idle_cores_per_time_step[time_step],
        )
