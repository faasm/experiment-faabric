from faasmctl.util.flush import flush_workers
from faasmctl.util.planner import reset as reset_planner
from invoke import task
from logging import getLogger, WARNING as log_level_WARNING
from os.path import join
from tasks.makespan.data import ExecutedTaskInfo
from tasks.makespan.scheduler import (
    BatchScheduler,
)
from tasks.makespan.trace import load_task_trace_from_file
from tasks.makespan.util import (
    ALLOWED_BASELINES,
    EXEC_TASK_INFO_FILE_PREFIX,
    GRANNY_BASELINES,
    IDLE_CORES_FILE_PREFIX,
    init_csv_file,
    get_idle_core_count_from_task_info,
    get_num_cpus_per_vm_from_trace,
    get_num_tasks_from_trace,
    get_trace_from_parameters,
    get_workload_from_trace,
    write_line_to_csv,
)
from tasks.util.env import RESULTS_DIR
from time import sleep
from typing import Dict

# imports to delete after test runs
from os.path import basename

# TODO(planner):
# from tasks.util.faasm import (
#   reset_planner,
#   wait_for_workers as wait_for_planner_workers,
# )
from tasks.lammps.env import get_faasm_benchmark
from tasks.util.faasm import post_async_msg_and_get_result_json

# Configure the logging settings globally
getLogger("requests").setLevel(log_level_WARNING)
getLogger("urllib3").setLevel(log_level_WARNING)


def _get_workload_from_cmdline(workload):
    base_workloads = ["mpi", "omp", "mix"]
    exp_workloads = ["mpi-migrate"]
    all_workloads = ["mix", "mpi", "mpi-migrate", "omp"]
    if workload == "all":
        workload = all_workloads
    elif workload == "base":
        workload = base_workloads
    elif workload == "exp":
        workload = exp_workloads
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
    workload="mpi",
    backend="k8s",
    num_vms=32,
    num_cpus_per_vm=8,
    num_tasks=100,
):
    """
    Run: `inv makespan.run.granny --workload [omp,mpi,mix,mpi-migrate,all]
    """
    workload = _get_workload_from_cmdline(workload)
    for wload in workload:
        trace = get_trace_from_parameters(wload, num_tasks, num_cpus_per_vm)
        _do_run(backend, "granny", num_vms, trace)
        sleep(5)


@task()
def native_slurm(
    ctx,
    workload="all",
    backend="k8s",
    num_vms=32,
    num_cpus_per_vm=8,
    num_tasks=100,
):
    """
    Run the native `slurm` baseline of the makespan experiment. The `slurm`
    baseline allocates resources at process/thread granularity
    """
    workload = _get_workload_from_cmdline(workload)
    for wload in workload:
        trace = get_trace_from_parameters(wload, num_tasks, num_cpus_per_vm)
        _do_run(
            backend,
            "slurm",
            num_vms,
            trace,
        )
        sleep(5)


@task()
def native_batch(
    ctx,
    workload="all",
    backend="k8s",
    num_vms=32,
    num_cpus_per_vm=8,
    num_tasks=100,
):
    """
    Run the native `batch` baseline of the makespan experiment. The `batch`
    baseline allocates resources at VM granularity
    """
    workload = _get_workload_from_cmdline(workload)
    for wload in workload:
        trace = get_trace_from_parameters(wload, num_tasks, num_cpus_per_vm)
        _do_run(
            backend,
            "batch",
            num_vms,
            trace,
        )
        sleep(5)


def _do_run(backend, baseline, num_vms, trace):
    num_vms = int(num_vms)
    job_workload = get_workload_from_trace(trace)
    num_tasks = get_num_tasks_from_trace(trace)
    num_cpus_per_vm = get_num_cpus_per_vm_from_trace(trace)

    if baseline not in ALLOWED_BASELINES:
        raise RuntimeError(
            "Unrecognised baseline: {} - Must be one in: {}".format(
                baseline, ALLOWED_BASELINES
            )
        )

    # Reset the planner and wait for the workers to register with it
    if baseline in GRANNY_BASELINES:
        reset_planner(num_vms)

    scheduler = BatchScheduler(
        backend,
        baseline,
        num_tasks,
        num_vms,
        trace,
    )

    init_csv_file(
        baseline,
        backend,
        num_vms,
        trace,
    )

    task_trace = load_task_trace_from_file(
        job_workload, num_tasks, num_cpus_per_vm
    )

    executed_task_info = scheduler.run(backend, baseline, task_trace)

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
            backend,
            IDLE_CORES_FILE_PREFIX,
            num_vms,
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
    backend="k8s",
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
    csv_name = "makespan_{}_{}_{}_{}_{}_{}_{}.csv".format(
        EXEC_TASK_INFO_FILE_PREFIX,
        baseline,
        backend,
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
            backend,
            IDLE_CORES_FILE_PREFIX,
            num_vms,
            trace,
            time_step,
            num_idle_cores_per_time_step[time_step],
        )


@task()
def migration_test(ctx):
    user = "lammps"
    func = "migration"
    data_file = get_faasm_benchmark("compute")["data"][0]
    cmdline = "-in faasm://lammps-data/{}".format(basename(data_file))

    # First, flush the host state
    flush_workers()

    msg = {
        "user": user,
        "function": func,
        "mpi": True,
        "mpi_world_size": 4,
        "async": True,
        "migration_check_period": 5,
        "cmdline": cmdline,
        "topology_hint": "UNDERFULL",
    }
    post_async_msg_and_get_result_json(msg)
