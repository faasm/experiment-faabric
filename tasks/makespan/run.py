from faasmctl.util.planner import reset as reset_planner, set_planner_policy
from invoke import task
from logging import getLogger, WARNING as log_level_WARNING
from os.path import join
from tasks.makespan.data import ExecutedTaskInfo
from tasks.makespan.scheduler import (
    BatchScheduler,
)
from tasks.util.env import RESULTS_DIR
from tasks.util.makespan import (
    ALLOWED_BASELINES,
    EXEC_TASK_INFO_FILE_PREFIX,
    GRANNY_BASELINES,
    IDLE_CORES_FILE_PREFIX,
    MAKESPAN_FILE_PREFIX,
    NATIVE_BASELINES,
    init_csv_file,
    get_idle_core_count_from_task_info,
    get_num_cpus_per_vm_from_trace,
    get_num_tasks_from_trace,
    get_trace_from_parameters,
    get_workload_from_trace,
    write_line_to_csv,
)
from tasks.util.trace import load_task_trace_from_file
from time import time
from typing import Dict

# Configure the logging settings globally
getLogger("requests").setLevel(log_level_WARNING)
getLogger("urllib3").setLevel(log_level_WARNING)


def _get_workload_from_cmdline(workload):
    # TODO: rename mpi-migrate to something like mpi-locality
    all_workloads = ["mpi-evict", "mpi-migrate", "mpi-spot", "omp-elastic"]

    if workload not in all_workloads:
        raise RuntimeError(
            "Unrecognised workload: {}. Must be one in: {}".format(
                workload, all_workloads
            )
        )

    return workload


@task()
def granny(
    ctx,
    workload="mpi-migrate",
    num_vms=32,
    num_cpus_per_vm=8,
    num_tasks=100,
    # Optional flag for mpi-migrate workload to migrate to improve locality
    migrate=False,
    # Optional flag for mpi-spot workload to inject faults
    fault=False,
    # Optional flag for omp-elastic workload to elastically use idle CPUs
    elastic=False,
    # Mandatory flag for the mpi-evict workload (not in the paper)
    num_users=None,
):
    """
    Run: `inv makespan.run.granny --workload [mpi-migrate,mpi-spot,omp-elastic]
    """
    # Work-out the baseline name from the arguments
    baseline = "granny"
    if migrate:
        assert (
            workload == "mpi-migrate"
        ), "--migrate flag should only be used with mpi-migrate workload!"
        baseline = "granny-migrate"
    if fault:
        assert (
            workload == "mpi-spot"
        ), "--fault flag should only be used with mpi-spot workload!"
        baseline = "granny-ft"
    if elastic:
        assert (
            workload == "omp-elastic"
        ), "--fault flag should only be used with omp-elastic workload!"
        baseline = "granny-elastic"

    workload = _get_workload_from_cmdline(workload)
    trace = get_trace_from_parameters(workload, num_tasks, num_cpus_per_vm)
    _do_run(baseline, num_vms, trace, num_users)


@task()
def native_slurm(
    ctx,
    workload="mpi-migrate",
    num_vms=32,
    num_cpus_per_vm=8,
    num_tasks=100,
    num_users=None,
    fault=False,
):
    """
    Run the native `slurm` baseline of the makespan experiment. The `slurm`
    baseline allocates resources at process/thread granularity
    """
    baseline = "slurm"
    if fault:
        baseline = "slurm-ft"

    workload = _get_workload_from_cmdline(workload)
    trace = get_trace_from_parameters(workload, num_tasks, num_cpus_per_vm)
    _do_run(
        baseline,
        num_vms,
        trace,
        num_users,
    )


@task()
def native_batch(
    ctx,
    workload="mpi-migrate",
    num_vms=32,
    num_cpus_per_vm=8,
    num_tasks=100,
    num_users=None,
    fault=False,
):
    """
    Run the native `batch` baseline of the makespan experiment. The `batch`
    baseline allocates resources at VM granularity
    """
    baseline = "batch"
    if fault:
        baseline = "batch-ft"

    workload = _get_workload_from_cmdline(workload)
    trace = get_trace_from_parameters(workload, num_tasks, num_cpus_per_vm)
    _do_run(
        baseline,
        num_vms,
        trace,
        num_users,
    )


def _do_run(baseline, num_vms, trace, num_users):
    num_vms = int(num_vms)
    job_workload = get_workload_from_trace(trace)
    num_tasks = get_num_tasks_from_trace(trace)
    num_cpus_per_vm = get_num_cpus_per_vm_from_trace(trace)

    if job_workload == "mpi-evict":
        num_users = 10 if num_users is None else int(num_users)
        num_tasks_per_user = int(num_tasks / num_users)
    else:
        num_tasks_per_user = None

    if baseline not in ALLOWED_BASELINES:
        raise RuntimeError(
            "Unrecognised baseline: {} - Must be one in: {}".format(
                baseline, ALLOWED_BASELINES
            )
        )

    # Reset the planner and wait for the workers to register with it
    if baseline in GRANNY_BASELINES:
        reset_planner(num_vms)

        if job_workload == "mpi-evict":
            set_planner_policy("compact")
        elif job_workload == "mpi-migrate":
            set_planner_policy("bin-pack")
        elif job_workload == "mpi-spot":
            set_planner_policy("spot")
        elif job_workload == "omp-elastic":
            set_planner_policy("bin-pack")

    scheduler = BatchScheduler(
        baseline,
        num_tasks,
        num_vms,
        num_tasks_per_user,
        trace,
    )

    if job_workload == "mpi-evict":
        init_csv_file(
            baseline,
            num_vms,
            trace,
            num_tasks_per_user=num_tasks_per_user,
        )
    else:
        init_csv_file(
            baseline,
            num_vms,
            trace,
        )

    task_trace = load_task_trace_from_file(
        job_workload, num_tasks, num_cpus_per_vm
    )

    start_ts = time()
    executed_task_info = scheduler.run(baseline, task_trace)
    makespan_secs = time() - start_ts

    # First of all, record the makespan (the total time elapsed)
    write_line_to_csv(
        baseline,
        MAKESPAN_FILE_PREFIX,
        num_vms,
        None,
        trace,
        makespan_secs,
    )

    # For granny we get the idle cores as we run the experiment, from the
    # planner (also, for the moment, we do not need these results for mpi-evict)
    if baseline in NATIVE_BASELINES and job_workload != "mpi-evict":
        num_idle_cores_per_time_step = get_idle_core_count_from_task_info(
            baseline,
            executed_task_info,
            task_trace,
            num_vms,
            num_cpus_per_vm,
        )
        for time_step in num_idle_cores_per_time_step:
            write_line_to_csv(
                baseline,
                IDLE_CORES_FILE_PREFIX,
                num_vms,
                None,
                trace,
                time_step,
                num_idle_cores_per_time_step[time_step],
            )

    # Finally shutdown the scheduler
    scheduler.shutdown()


@task()
def idle_cores_from_exec_task(
    ctx,
    baseline,
    workload,
    num_vms=32,
    num_tasks=100,
    num_cpus_per_vm=8,
):
    result_dir = join(RESULTS_DIR, "makespan")
    executed_task_info: Dict[int, ExecutedTaskInfo] = {}

    num_vms = int(num_vms)
    num_tasks = int(num_tasks)

    trace = get_trace_from_parameters(workload, num_tasks, num_cpus_per_vm)
    job_workload = get_workload_from_trace(trace)
    num_tasks = int(get_num_tasks_from_trace(trace))
    num_cpus_per_vm = int(get_num_cpus_per_vm_from_trace(trace))

    # Get executed task info from file
    csv_name = "makespan_{}_{}_{}_{}_{}_{}.csv".format(
        EXEC_TASK_INFO_FILE_PREFIX,
        baseline,
        num_vms,
        workload,
        num_tasks,
        num_cpus_per_vm,
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
        job_workload, num_tasks, num_cpus_per_vm
    )
    num_idle_cores_per_time_step = get_idle_core_count_from_task_info(
        executed_task_info,
        task_trace,
        num_vms,
        num_cpus_per_vm,
        granny,
    )
    for time_step in num_idle_cores_per_time_step:
        write_line_to_csv(
            baseline,
            IDLE_CORES_FILE_PREFIX,
            num_vms,
            trace,
            time_step,
            num_idle_cores_per_time_step[time_step],
        )
