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
    get_trace_from_parameters,
    get_workload_from_trace,
    write_line_to_csv,
)
from tasks.util.env import RESULTS_DIR
from time import sleep
from typing import Dict


def _get_workload_from_cmdline(workload):
    all_workloads = ["mpi", "mpi-migrate", "omp"]
    if workload == "all":
        workload = all_workloads
    elif workload in all_workloads:
        workload = [workload]
    else:
        raise RuntimeError(
            "Unrecognised workload: {}. Must be one in: {}".format(
                workload, all_workloads
            )
        )
    return workload


@task()
def granny(
    ctx,
    workload="all",
    backend="k8s",
    num_vms=32,
    num_cores_per_vm=8,
    num_tasks=100,
):
    """
    Run: `inv makespan.run.native --workload [omp,mpi,mpi-migrate,all]
    """
    workload = _get_workload_from_cmdline(workload)
    for wload in workload:
        trace = get_trace_from_parameters(wload, num_tasks, num_cores_per_vm)
        _do_run(backend=backend, num_vms=num_vms, granny=True, trace=trace)
        sleep(5)


@task()
def native(
    ctx,
    workload="all",
    backend="k8s",
    num_vms=32,
    num_cores_per_vm=8,
    num_tasks=100,
    ctrs_per_vm=1,
):
    """
    Run: `inv makespan.run.native --workload [omp,mpi,mpi-migrate,all] --ctrs-per-vm <>
    """
    workload = _get_workload_from_cmdline(workload)
    for wload in workload:
        trace = get_trace_from_parameters(wload, num_tasks, num_cores_per_vm)
        _do_run(
            backend=backend,
            num_vms=num_vms,
            ctrs_per_vm=ctrs_per_vm,
            trace=trace,
        )
        sleep(5)


def _do_run(
    backend="k8s",
    num_vms=32,
    ctrs_per_vm=1,
    granny=False,
    trace=None,
):
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
        trace,
    )

    init_csv_file(
        workload,
        backend,
        num_vms,
        trace,
        ctrs_per_vm,
    )

    task_trace = load_task_trace_from_file(
        job_workload, num_tasks, num_cores_per_vm
    )

    executed_task_info = scheduler.run(backend, workload, task_trace)

    num_idle_cores_per_time_step = get_idle_core_count_from_task_info(
        executed_task_info,
        task_trace,
        num_vms,
        num_cores_per_vm,
        ctrs_per_vm,
        granny,
    )
    for time_step in num_idle_cores_per_time_step:
        write_line_to_csv(
            workload,
            backend,
            IDLE_CORES_FILE_PREFIX,
            num_vms,
            trace,
            ctrs_per_vm,
            time_step,
            num_idle_cores_per_time_step[time_step],
        )

    # Finally shutdown the scheduler
    scheduler.shutdown()


@task()
def idle_cores_from_exec_task(
    ctx,
    workload,
    backend="k8s",
    num_vms=32,
    ctrs_per_vm=1,
    num_tasks=100,
    num_cores_per_vm=8,
    granny=False,
):
    result_dir = join(RESULTS_DIR, "makespan")
    executed_task_info: Dict[int, ExecutedTaskInfo] = {}

    num_vms = int(num_vms)
    ctrs_per_vm = int(ctrs_per_vm)
    num_tasks = int(num_tasks)

    trace = get_trace_from_parameters(workload, num_tasks, num_cores_per_vm)
    job_workload = get_workload_from_trace(trace)
    num_tasks = int(get_num_tasks_from_trace(trace))
    num_cores_per_vm = int(get_num_cores_from_trace(trace))

    if granny:
        system = "granny"
    else:
        system = "native-{}".format(ctrs_per_vm)

    # Get executed task info from file
    csv_name = "makespan_{}_{}_{}_{}_{}_{}_{}.csv".format(
        EXEC_TASK_INFO_FILE_PREFIX,
        system,
        backend,
        num_vms,
        workload,
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
        executed_task_info,
        task_trace,
        num_vms,
        num_cores_per_vm,
        ctrs_per_vm,
        granny,
    )
    for time_step in num_idle_cores_per_time_step:
        write_line_to_csv(
            system,
            backend,
            IDLE_CORES_FILE_PREFIX,
            num_vms,
            trace,
            ctrs_per_vm,
            time_step,
            num_idle_cores_per_time_step[time_step],
        )
