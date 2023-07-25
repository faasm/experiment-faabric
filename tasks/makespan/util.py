from math import ceil, floor
from os import makedirs
from os.path import join
from tasks.util.env import (
    RESULTS_DIR,
)
from tasks.util.openmpi import get_native_mpi_pods_ip_to_vm

IDLE_CORES_FILE_PREFIX = "idle-cores"
EXEC_TASK_INFO_FILE_PREFIX = "exec-task-info"
SCHEDULINNG_INFO_FILE_PREFIX = "sched-info"

# Allowed system baselines:
# - Granny: is our system
# - Batch: native OpenMPI where we schedule jobs at VM granularity
# - Slurm: native OpenMPI where we schedule jobs at process granularity
NATIVE_BASELINES = ["batch", "slurm"]
GRANNY_BASELINES = ["granny"]
ALLOWED_BASELINES = NATIVE_BASELINES + GRANNY_BASELINES


def init_csv_file(baseline, backend, num_vms, trace_str):
    result_dir = join(RESULTS_DIR, "makespan")
    makedirs(result_dir, exist_ok=True)

    # Idle Cores file
    csv_name_ic = "makespan_{}_{}_{}_{}_{}".format(
        IDLE_CORES_FILE_PREFIX,
        baseline,
        backend,
        num_vms,
        get_trace_ending(trace_str),
    )
    ic_file = join(result_dir, csv_name_ic)
    with open(ic_file, "w") as out_file:
        out_file.write("TimeStampSecs,NumIdleCores\n")

    # Executed task info file
    csv_name = "makespan_{}_{}_{}_{}_{}".format(
        EXEC_TASK_INFO_FILE_PREFIX,
        baseline,
        backend,
        num_vms,
        get_trace_ending(trace_str),
    )
    csv_file = join(result_dir, csv_name)
    with open(csv_file, "w") as out_file:
        out_file.write(
            "TaskId,TimeExecuting,TimeInQueue,StartTimeStamp,EndTimeStamp\n"
        )

    # Schedulign info file (this file is only used for the motivation plot with
    # native baselines)
    if baseline in NATIVE_BASELINES and backend == "k8s":
        csv_name = "makespan_{}_{}_{}_{}_{}".format(
            SCHEDULINNG_INFO_FILE_PREFIX,
            baseline,
            backend,
            num_vms,
            get_trace_ending(trace_str),
        )
        csv_file = join(result_dir, csv_name)
        with open(csv_file, "w") as out_file:
            out_file.write("TaskId,SchedulingDecision\n")
            ips, vms = get_native_mpi_pods_ip_to_vm("makespan")
            ip_to_vm = ["{},{}".format(ip, vm) for ip, vm in zip(ips, vms)]
            out_file.write(",".join(ip_to_vm) + "\n")


def write_line_to_csv(baseline, backend, exp_key, num_vms, trace_str, *args):
    result_dir = join(RESULTS_DIR, "makespan")
    if exp_key == IDLE_CORES_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}_{}".format(
            IDLE_CORES_FILE_PREFIX,
            baseline,
            backend,
            num_vms,
            get_trace_ending(trace_str),
        )
        makespan_file = join(result_dir, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{}\n".format(*args))
    elif exp_key == EXEC_TASK_INFO_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}_{}".format(
            EXEC_TASK_INFO_FILE_PREFIX,
            baseline,
            backend,
            num_vms,
            get_trace_ending(trace_str),
        )
        makespan_file = join(result_dir, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{},{},{},{}\n".format(*args))
    elif exp_key == SCHEDULINNG_INFO_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}_{}".format(
            SCHEDULINNG_INFO_FILE_PREFIX,
            baseline,
            backend,
            num_vms,
            get_trace_ending(trace_str),
        )
        makespan_file = join(result_dir, csv_name)
        task_id = args[0]
        task_sched = ["{},{}".format(ip, slots) for (ip, slots) in args[1]]
        sched_str = ",".join([str(task_id)] + task_sched)
        with open(makespan_file, "a") as out_file:
            out_file.write("{}\n".format(sched_str))


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
