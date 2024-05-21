from math import ceil, floor
from os import makedirs
from os.path import join
from tasks.util.env import (
    PLOTS_ROOT,
    RESULTS_DIR,
)
from tasks.util.openmpi import get_native_mpi_pods_ip_to_vm

# Directories
MAKESPAN_RESULTS_DIR = join(RESULTS_DIR, "makespan")
MAKESPAN_PLOTS_DIR = join(PLOTS_ROOT, "makespan")

# Result files
IDLE_CORES_FILE_PREFIX = "idle-cores"
EXEC_TASK_INFO_FILE_PREFIX = "exec-task-info"
SCHEDULING_INFO_FILE_PREFIX = "sched-info"
MAKESPAN_FILE_PREFIX = "makespan"

# Allowed system baselines:
# - Granny: is our system
# - Batch: native OpenMPI where we schedule jobs at VM granularity
# - Slurm: native OpenMPI where we schedule jobs at CPU core granularity
NATIVE_FT_BASELINES = ["batch-ft", "slurm-ft"]
NATIVE_BASELINES = ["batch", "slurm"] + NATIVE_FT_BASELINES
GRANNY_BATCH_BASELINES = ["granny-batch"]
GRANNY_ELASTIC_BASELINES = ["granny-elastic"]
GRANNY_FT_BASELINES = ["granny-ft"]
GRANNY_MIGRATE_BASELINES = ["granny-migrate"]
GRANNY_BASELINES = (
    ["granny"]
    + GRANNY_BATCH_BASELINES
    + GRANNY_MIGRATE_BASELINES
    + GRANNY_FT_BASELINES
    + GRANNY_ELASTIC_BASELINES
)
ALLOWED_BASELINES = NATIVE_BASELINES + GRANNY_BASELINES

# Workload/Migration related constants
MPI_MIGRATE_WORKLOADS = ["mpi-locality", "mpi-evict", "mpi-spot"]
MPI_WORKLOADS = ["mpi"] + MPI_MIGRATE_WORKLOADS
OPENMP_WORKLOADS = ["omp", "omp-elastic"]


def init_csv_file(baseline, num_vms, trace_str, num_tasks_per_user=None):
    makedirs(MAKESPAN_RESULTS_DIR, exist_ok=True)

    # Idle Cores file
    csv_name_ic = "makespan_{}_{}_{}_{}".format(
        IDLE_CORES_FILE_PREFIX,
        baseline,
        num_vms
        if num_tasks_per_user is None
        else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
        get_trace_ending(trace_str),
    )
    ic_file = join(MAKESPAN_RESULTS_DIR, csv_name_ic)
    with open(ic_file, "w") as out_file:
        out_file.write("TimeStampSecs,NumIdleCores\n")

    # Executed task info file
    csv_name = "makespan_{}_{}_{}_{}".format(
        EXEC_TASK_INFO_FILE_PREFIX,
        baseline,
        num_vms
        if num_tasks_per_user is None
        else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
        get_trace_ending(trace_str),
    )
    csv_file = join(MAKESPAN_RESULTS_DIR, csv_name)
    with open(csv_file, "w") as out_file:
        out_file.write(
            "TaskId,TimeExecuting,TimeInQueue,StartTimeStamp,EndTimeStamp\n"
        )

    # Scheduling info file. This file is different for native baselines and
    # for Granny. As in Granny we get this information from the planner
    csv_name = "makespan_{}_{}_{}_{}".format(
        SCHEDULING_INFO_FILE_PREFIX,
        baseline,
        num_vms
        if num_tasks_per_user is None
        else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
        get_trace_ending(trace_str),
    )
    csv_file = join(MAKESPAN_RESULTS_DIR, csv_name)
    if baseline in NATIVE_BASELINES:
        with open(csv_file, "w") as out_file:
            out_file.write("TaskId,SchedulingDecision\n")
            ips, vms = get_native_mpi_pods_ip_to_vm("makespan")
            ip_to_vm = ["{},{}".format(ip, vm) for ip, vm in zip(ips, vms)]
            out_file.write(",".join(ip_to_vm) + "\n")
    else:
        with open(csv_file, "w") as out_file:
            out_file.write(
                "TimeStampSecs,NumIdleVms,NumIdleCpus,NumCrossVmLinks\n"
            )
            out_file.write

    # Makespan file
    # In some fault-tolerant baselines we cannot only rely on the executed task
    # info to get the end-to-end latency measurement as some tasks may fail.
    # Instead, we use a CSV file too
    csv_name = "makespan_{}_{}_{}_{}".format(
        MAKESPAN_FILE_PREFIX,
        baseline,
        num_vms
        if num_tasks_per_user is None
        else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
        get_trace_ending(trace_str),
    )
    csv_file = join(MAKESPAN_RESULTS_DIR, csv_name)
    with open(csv_file, "w") as out_file:
        out_file.write("MakespanSecs\n")


def write_line_to_csv(
    baseline, exp_key, num_vms, num_tasks_per_user, trace_str, *args
):
    if exp_key == IDLE_CORES_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}".format(
            IDLE_CORES_FILE_PREFIX,
            baseline,
            num_vms
            if num_tasks_per_user is None
            else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
            get_trace_ending(trace_str),
        )
        makespan_file = join(MAKESPAN_RESULTS_DIR, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{}\n".format(*args))
    elif exp_key == EXEC_TASK_INFO_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}".format(
            EXEC_TASK_INFO_FILE_PREFIX,
            baseline,
            num_vms
            if num_tasks_per_user is None
            else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
            get_trace_ending(trace_str),
        )
        makespan_file = join(MAKESPAN_RESULTS_DIR, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{},{},{},{}\n".format(*args))
    elif exp_key == SCHEDULING_INFO_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}".format(
            SCHEDULING_INFO_FILE_PREFIX,
            baseline,
            num_vms
            if num_tasks_per_user is None
            else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
            get_trace_ending(trace_str),
        )
        makespan_file = join(MAKESPAN_RESULTS_DIR, csv_name)
        if baseline in NATIVE_BASELINES:
            task_id = args[0]
            task_sched = ["{},{}".format(ip, slots) for (ip, slots) in args[1]]
            sched_str = ",".join([str(task_id)] + task_sched)
            with open(makespan_file, "a") as out_file:
                out_file.write("{}\n".format(sched_str))
        else:
            with open(makespan_file, "a") as out_file:
                out_file.write("{},{},{},{}\n".format(*args))
    elif exp_key == MAKESPAN_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}".format(
            MAKESPAN_FILE_PREFIX,
            baseline,
            num_vms
            if num_tasks_per_user is None
            else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
            get_trace_ending(trace_str),
        )
        makespan_file = join(MAKESPAN_RESULTS_DIR, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{}\n".format(*args))


# ----------------------------
# Trace file name manipulation
# ----------------------------


def get_trace_ending(trace_str):
    return trace_str[6:]


def get_workload_from_trace(trace_str):
    """
    Get workload from trace string
    """
    return trace_str.split("_")[1]


def get_num_tasks_from_trace(trace_str):
    """
    Get number of tasks from trace string
    """
    return int(trace_str.split("_")[2])


def get_num_cpus_per_vm_from_trace(trace_str):
    """
    Get number of cpus per VM from trace string
    """
    return int(trace_str.split("_")[3][:-4])


def get_trace_from_parameters(workload, num_tasks=100, num_cpus_per_vm=8):
    return "trace_{}_{}_{}.csv".format(workload, num_tasks, num_cpus_per_vm)


# ----------------------------
# Idle core's utilities
# ----------------------------


def get_user_id_from_task(num_tasks_per_user, task_id):
    if num_tasks_per_user is None:
        return None

    return int(task_id / num_tasks_per_user) + 1


def get_idle_core_count_from_task_info(
    baseline,
    executed_task_info,
    task_trace,
    num_vms,
    num_cpus_per_vm,
):
    """
    Given a map of <task_id, ExecutedTaskInfo> work out the number of idle
    cores in the system from the first task's start timestap, to the last
    task's end timestamp. This method is quite inneficient in terms of
    complexity, but it happens post-mortem so unless its very bad we don't
    really care
    """
    # First, work out the total time elapsed between all the executed tasks
    # and divide it in one second slots
    min_start_ts = min(
        [et.exec_start_ts for et in executed_task_info.values()]
    )
    max_end_ts = max([et.exec_end_ts for et in executed_task_info.values()])
    time_elapsed_secs = int(max_end_ts - min_start_ts)
    if time_elapsed_secs > 1e5:
        raise RuntimeError(
            "Measured total time elapsed is too long: {}".format(
                time_elapsed_secs
            )
        )

    # Initialise each time slot to the maximum number of cores
    num_idle_cores_per_time_step = {}
    for ts in range(time_elapsed_secs):
        num_idle_cores_per_time_step[ts] = num_vms * num_cpus_per_vm

    # Then, for each task, subtract its size to all the seconds it elapsed. We
    # are conservative here and round up for start times, and down for end
    # times. If this becomes a problem, we can always use a smaller time
    # differential
    for task_id in executed_task_info:
        # Retrieve original task and assert it is the right one
        task = task_trace[task_id]
        if task.task_id != task_id:
            print(
                "Error processing tasks. Expected id {} - got {}".format(
                    task_id, task.task_id
                )
            )
            raise RuntimeError("Error processing tasks")

        task_size = task.size
        # In a native OpenMP task, we may have overcommited to a smaller number
        # of cores. Given that we don't distribute OpenMP jobs, it is safe to
        # just subtract the container size in case of overcomitment
        if task.app == "omp" and not baseline == "granny":
            task_size = min(task.size, num_cpus_per_vm)

        # Get the start and end ts as offsets from our global minimum timestamp
        start_t = executed_task_info[task_id].exec_start_ts - min_start_ts
        end_t = executed_task_info[task_id].exec_end_ts - min_start_ts

        # Be conservative, and round the start timestamp up and the end
        # timestamp down to prevent double-counting
        start_t = ceil(start_t)
        end_t = floor(end_t)

        # Finally, subtract the task size from all the time slots during which
        # the task was in-flight
        while start_t < end_t:
            if start_t not in num_idle_cores_per_time_step:
                raise RuntimeError(
                    "Time differential ({}) not in range!".format(start_t)
                )
            num_idle_cores_per_time_step[start_t] -= task_size
            start_t += 1

    return num_idle_cores_per_time_step
