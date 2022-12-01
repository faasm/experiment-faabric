from math import ceil, floor
from os import makedirs
from os.path import join
from tasks.util.env import (
    RESULTS_DIR,
)

IDLE_CORES_FILE_PREFIX = "idle-cores"
EXEC_TASK_INFO_FILE_PREFIX = "exec-task-info"


def init_csv_file(workload, backend, num_vms, trace_str, ctrs_per_vm):
    result_dir = join(RESULTS_DIR, "makespan")
    makedirs(result_dir, exist_ok=True)

    if workload == "native":
        workload = "native-{}".format(ctrs_per_vm)

    # Idle Cores file
    csv_name_ic = "makespan_{}_{}_{}_{}_{}".format(
        IDLE_CORES_FILE_PREFIX,
        workload,
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
        workload,
        backend,
        num_vms,
        get_trace_ending(trace_str),
    )
    csv_file = join(result_dir, csv_name)
    with open(csv_file, "w") as out_file:
        out_file.write(
            "TaskId,TimeExecuting,TimeInQueue,StartTimeStamp,EndTimeStamp\n"
        )


def write_line_to_csv(
    workload, backend, exp_key, num_vms, trace_str, ctrs_per_vm, *args
):
    # TODO: this method could be simplified and more code reused
    if workload == "native":
        workload = "native-{}".format(ctrs_per_vm)

    result_dir = join(RESULTS_DIR, "makespan")
    if exp_key == IDLE_CORES_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}_{}".format(
            IDLE_CORES_FILE_PREFIX,
            workload,
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
            workload,
            backend,
            num_vms,
            get_trace_ending(trace_str),
        )
        makespan_file = join(result_dir, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{},{},{},{}\n".format(*args))


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


def get_num_cores_from_trace(trace_str):
    """
    Get number of cores from trace string
    """
    return int(trace_str.split("_")[3][:-4])


def get_trace_from_parameters(workload, num_tasks=100, num_cores_per_vm=8):
    return "trace_{}_{}_{}.csv".format(workload, num_tasks, num_cores_per_vm)


# ----------------------------
# Idle core's utilities
# ----------------------------


def get_idle_core_count_from_task_info(
    executed_task_info,
    task_trace,
    num_vms,
    num_cores_per_vm,
    ctrs_per_vm,
    is_granny,
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
    num_cores_per_ctr = int(num_cores_per_vm / ctrs_per_vm)
    num_idle_cores_per_time_step = {}
    for ts in range(time_elapsed_secs):
        num_idle_cores_per_time_step[ts] = num_vms * num_cores_per_vm

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
        if task.app == "omp" and not is_granny:
            task_size = min(task.size, num_cores_per_ctr)

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
