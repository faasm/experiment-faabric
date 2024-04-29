from glob import glob
from math import ceil, floor
from matplotlib.patches import Patch, Polygon
from numpy import linspace
from os import makedirs
from os.path import join
from pandas import read_csv
from scipy.interpolate import CubicSpline
from tasks.util.trace import load_task_trace_from_file
from tasks.util.env import (
    PLOTS_ROOT,
    RESULTS_DIR,
)
from tasks.util.planner import get_xvm_links_from_part
from tasks.util.openmpi import get_native_mpi_pods_ip_to_vm
from tasks.util.plot import PLOT_COLORS

# Directories
MAKESPAN_RESULTS_DIR = join(RESULTS_DIR, "makespan")
MAKESPAN_PLOTS_DIR = join(PLOTS_ROOT, "makespan")

# Result files
IDLE_CORES_FILE_PREFIX = "idle-cores"
EXEC_TASK_INFO_FILE_PREFIX = "exec-task-info"
SCHEDULING_INFO_FILE_PREFIX = "sched-info"

# Allowed system baselines:
# - Granny: is our system
# - Batch: native OpenMPI where we schedule jobs at VM granularity
# - Slurm: native OpenMPI where we schedule jobs at CPU core granularity
NATIVE_FT_BASELINES = ["batch-ft", "slutm-ft"]
NATIVE_BASELINES = ["batch", "slurm"] + NATIVE_FT_BASELINES
GRANNY_FT_BASELINES = ["granny-ft"]
GRANNY_MIGRATE_BASELINES = ["granny-migrate"]
GRANNY_BASELINES = ["granny"] + GRANNY_MIGRATE_BASELINES + GRANNY_FT_BASELINES
ALLOWED_BASELINES = NATIVE_BASELINES + GRANNY_BASELINES

# Workload/Migration related constants
MPI_MIGRATE_WORKLOADS = ["mpi-migrate", "mpi-evict", "mpi-spot"]
MPI_WORKLOADS = ["mpi"] + MPI_MIGRATE_WORKLOADS


def cum_sum(ts, values):
    """
    Perform the cumulative sum of the values (i.e. integral) over the time
    interval defined by ts
    """
    assert len(ts) == len(values), "Can't CumSum over different sizes!({} != {})".format(len(ts), len(values))

    cum_sum = 0
    prev_t = ts[0]
    prev_val = values[0]
    for i in range(1, len(ts)):
        base = ts[i] - prev_t
        cum_sum += base * prev_val

        prev_t = ts[i]
        prev_val = values[i]

    # We discard the last value, but that is OK
    return cum_sum


def init_csv_file(baseline, num_vms, trace_str, num_tasks_per_user=None):
    makedirs(MAKESPAN_RESULTS_DIR, exist_ok=True)

    # Idle Cores file
    csv_name_ic = "makespan_{}_{}_{}_{}".format(
        IDLE_CORES_FILE_PREFIX,
        baseline,
        num_vms if num_tasks_per_user is None else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
        get_trace_ending(trace_str),
    )
    ic_file = join(MAKESPAN_RESULTS_DIR, csv_name_ic)
    with open(ic_file, "w") as out_file:
        out_file.write("TimeStampSecs,NumIdleCores\n")

    # Executed task info file
    csv_name = "makespan_{}_{}_{}_{}".format(
        EXEC_TASK_INFO_FILE_PREFIX,
        baseline,
        num_vms if num_tasks_per_user is None else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
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
        num_vms if num_tasks_per_user is None else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
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
            out_file.write("TimeStampSecs,NumIdleVms,NumIdleCpus,NumCrossVmLinks\n")
            out_file.write


def write_line_to_csv(baseline, exp_key, num_vms, num_tasks_per_user, trace_str, *args):
    if exp_key == IDLE_CORES_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}".format(
            IDLE_CORES_FILE_PREFIX,
            baseline,
            num_vms if num_tasks_per_user is None else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
            get_trace_ending(trace_str),
        )
        makespan_file = join(MAKESPAN_RESULTS_DIR, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{}\n".format(*args))
    elif exp_key == EXEC_TASK_INFO_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}".format(
            EXEC_TASK_INFO_FILE_PREFIX,
            baseline,
            num_vms if num_tasks_per_user is None else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
            get_trace_ending(trace_str),
        )
        makespan_file = join(MAKESPAN_RESULTS_DIR, csv_name)
        with open(makespan_file, "a") as out_file:
            out_file.write("{},{},{},{},{}\n".format(*args))
    elif exp_key == SCHEDULING_INFO_FILE_PREFIX:
        csv_name = "makespan_{}_{}_{}_{}".format(
            SCHEDULING_INFO_FILE_PREFIX,
            baseline,
            num_vms if num_tasks_per_user is None else "{}vms_{}tpusr".format(num_vms, num_tasks_per_user),
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

# ----------------------------
# Plotting utilities
# ----------------------------

def read_makespan_results(num_vms, num_tasks, num_cpus_per_vm):
    workload = "mpi-migrate"

    # Load results
    result_dict = {}
    glob_str = "makespan_exec-task-info_*_{}_{}_{}_{}.csv".format(
        num_vms, workload, num_tasks, num_cpus_per_vm
    )
    for csv in glob(join(MAKESPAN_RESULTS_DIR, glob_str)):
        baseline = csv.split("_")[2]
        workload = csv.split("_")[4]

        # -----
        # Results to visualise differences between execution time and time
        # in queue
        # -----

        # Results for per-job exec time and time-in-queue
        result_dict[baseline] = {}
        results = read_csv(csv)
        task_ids = results["TaskId"].to_list()
        times_exec = results["TimeExecuting"].to_list()
        times_queue = results["TimeInQueue"].to_list()
        start_ts = results["StartTimeStamp"].to_list()
        genesis_ts = min(start_ts)
        end_ts = results["EndTimeStamp"].to_list()
        result_dict[baseline]["exec-time"] = [-1 for _ in task_ids]
        result_dict[baseline]["queue-time"] = [-1 for _ in task_ids]
        result_dict[baseline]["jct"] = [-1 for _ in task_ids]

        for tid, texec, tqueue, e_ts in zip(
            task_ids, times_exec, times_queue, end_ts
        ):
            result_dict[baseline]["exec-time"][tid] = texec
            result_dict[baseline]["queue-time"][tid] = tqueue
            result_dict[baseline]["jct"][tid] = e_ts - genesis_ts

        # -----
        # Results to visualise job churn
        # -----

        start_ts = results.min()["StartTimeStamp"]
        end_ts = results.max()["EndTimeStamp"]
        time_elapsed_secs = int(end_ts - start_ts)
        result_dict[baseline]["makespan"] = time_elapsed_secs
        print(
            "Num VMs: {} - Num Tasks: {} - Baseline: {} - Makespan: {}s".format(
                num_vms, num_tasks, baseline, time_elapsed_secs
            )
        )
        if time_elapsed_secs > 1e5:
            raise RuntimeError(
                "Measured total time elapsed is too long: {}".format(
                    time_elapsed_secs
                )
            )

        # Dump all data
        tasks_per_ts = [[] for i in range(time_elapsed_secs)]
        for index, row in results.iterrows():
            task_id = row["TaskId"]
            start_slot = int(row["StartTimeStamp"] - start_ts)
            end_slot = int(row["EndTimeStamp"] - start_ts)
            for ind in range(start_slot, end_slot):
                tasks_per_ts[ind].append(task_id)
        for tasks in tasks_per_ts:
            tasks.sort()

        # Prune the timeseries
        pruned_tasks_per_ts = {}
        # prev_tasks = []
        for ts, tasks in enumerate(tasks_per_ts):
            # NOTE: we are not pruning at the moment
            pruned_tasks_per_ts[ts] = tasks
            # if tasks != prev_tasks:
            # pruned_tasks_per_ts[ts] = tasks
            # prev_tasks = tasks

        result_dict[baseline]["tasks_per_ts"] = pruned_tasks_per_ts

        # -----
        # Results to visualise scheduling info per task
        # -----

        sched_info_csv = "makespan_sched-info_{}_{}_{}_{}_{}.csv".format(
                baseline, num_vms, workload, num_tasks, num_cpus_per_vm
        )
        if baseline not in GRANNY_BASELINES:
            result_dict[baseline]["task_scheduling"] = {}

            # We identify VMs by numbers, not IPs
            ip_to_vm = {}
            vm_to_id = {}
            with open(join(MAKESPAN_RESULTS_DIR, sched_info_csv), "r") as sched_fd:
                # Process the file line by line, as each line will be different in
                # length
                for num, line in enumerate(sched_fd):
                    # Skip the header
                    if num == 0:
                        continue

                    line = line.strip()

                    # In line 1 we include the IP to node conversion as one
                    # comma-separated line, so we parse it here
                    if num == 1:
                        ip_to_vm_line = line.split(",")
                        assert len(ip_to_vm_line) % 2 == 0

                        i = 0
                        while i < len(ip_to_vm_line):
                            ip = ip_to_vm_line[i]
                            vm = ip_to_vm_line[i + 1]
                            ip_to_vm[ip] = vm
                            i += 2

                        continue

                    # Get the task id and the scheduling decision from the line
                    task_id = line.split(",")[0]
                    result_dict[baseline]["task_scheduling"][task_id] = {}
                    sched_info = line.split(",")[1:]
                    # The scheduling decision must be even, as it contains pairs
                    # of ip + slots
                    assert len(sched_info) % 2 == 0

                    i = 0
                    while i < len(sched_info):
                        vm = ip_to_vm[sched_info[i]]
                        slots = sched_info[i + 1]

                        if vm not in vm_to_id:
                            len_map = len(vm_to_id)
                            vm_to_id[vm] = len_map

                        vm_id = vm_to_id[vm]
                        if (
                            vm_id
                            not in result_dict[baseline]["task_scheduling"][
                                task_id
                            ]
                        ):
                            result_dict[baseline]["task_scheduling"][task_id][
                                vm_id
                            ] = 0

                        result_dict[baseline]["task_scheduling"][task_id][
                            vm_id
                        ] += int(slots)
                        i += 2

        # -----
        # Results to visualise the % of idle vCPUs (and VMs) over time
        # -----

        task_trace = load_task_trace_from_file(
            workload, num_tasks, num_cpus_per_vm
        )

        result_dict[baseline]["ts_vcpus"] = {}
        result_dict[baseline]["ts_xvm_links"] = {}
        result_dict[baseline]["ts_idle_vms"] = {}
        total_available_vcpus = num_vms * num_cpus_per_vm

        if baseline in NATIVE_BASELINES:
            # First, set each timestamp to the total available vCPUs, and
            # initialise the set of idle vms
            for ts in result_dict[baseline]["tasks_per_ts"]:
                result_dict[baseline]["ts_vcpus"][ts] = total_available_vcpus
                result_dict[baseline]["ts_idle_vms"][ts] = set()

            # Second, for each ts subtract the size of each task in-flight
            for ts in result_dict[baseline]["tasks_per_ts"]:
                for t in result_dict[baseline]["tasks_per_ts"][ts]:
                    result_dict[baseline]["ts_vcpus"][ts] -= task_trace[
                        int(t)
                    ].size

                    # In addition, for each task in flight, add the tasks's IPs
                    # to the host set
                    for vm_id in result_dict[baseline]["task_scheduling"][str(int(t))]:
                        result_dict[baseline]["ts_idle_vms"][ts].add(vm_id)

            # Third, express the results as percentages, and the number of
            # idle VMs as a number (not as a set)
            for ts in result_dict[baseline]["ts_vcpus"]:
                result_dict[baseline]["ts_vcpus"][ts] = (
                    result_dict[baseline]["ts_vcpus"][ts] / total_available_vcpus
                ) * 100

                result_dict[baseline]["ts_idle_vms"][ts] = num_vms - len(result_dict[baseline]["ts_idle_vms"][ts])
        else:
            # For Granny, the idle vCPUs results are directly available in
            # the file
            sch_info_csv = read_csv(join(MAKESPAN_RESULTS_DIR, sched_info_csv))
            idle_cpus = (sch_info_csv["NumIdleCpus"] / total_available_vcpus * 100).to_list()
            tss = (sch_info_csv["TimeStampSecs"] - sch_info_csv["TimeStampSecs"][0]).to_list()

            # Idle vCPUs
            for (idle_cpu, ts) in zip(idle_cpus, tss):
                result_dict[baseline]["ts_vcpus"][ts] = idle_cpu

            # x-VM links
            xvm_links = sch_info_csv["NumCrossVmLinks"].to_list()
            for (ts, xvm_link) in zip(tss, xvm_links):
                result_dict[baseline]["ts_xvm_links"][ts] = xvm_link

            # Num of idle VMs
            num_idle_vms = sch_info_csv["NumIdleVms"].to_list()
            for (ts, n_idle_vms) in zip(tss, num_idle_vms):
                result_dict[baseline]["ts_idle_vms"][ts] = n_idle_vms

        # -----
        # Results to visualise the # of cross-vm links
        # -----

        if baseline in NATIVE_BASELINES:
            for ts in result_dict[baseline]["tasks_per_ts"]:
                result_dict[baseline]["ts_xvm_links"][ts] = 0

            for ts in result_dict[baseline]["tasks_per_ts"]:
                for t in result_dict[baseline]["tasks_per_ts"][ts]:
                    if baseline == "slurm":
                        sched = result_dict[baseline]["task_scheduling"][
                            str(int(t))
                        ]

                        # If only scheduled to one VM, no cross-VM links
                        if len(sched) <= 1:
                            continue

                        # Add the accumulated to the total tally
                        result_dict[baseline]["ts_xvm_links"][ts] += get_xvm_links_from_part(list(sched.values()))
                    elif baseline == "batch":
                        # Batch baseline is optimal in terms of cross-vm links
                        task_size = task_trace[int(t)].size
                        if task_size > 8:
                            num_links = 8 * (task_size - 8) / 2
                            result_dict[baseline]["ts_xvm_links"][
                                ts
                            ] += num_links

    return result_dict


def fix_hist_step_vertical_line_at_end(ax):
    axpolygons = [
        poly for poly in ax.get_children() if isinstance(poly, Polygon)
    ]
    for poly in axpolygons:
        poly.set_xy(poly.get_xy()[:-1])


def do_makespan_plot(plot_name, results, ax, num_vms, num_tasks):
    """
    This method keeps track of all the different alternative plots we have
    explored for the motivation figure.
    """

    if plot_name == "exec_vs_tiq":
        """
        This plot presents the percentiles of slowdown of execution time (and
        time in queue too?)
        """
        num_jobs = len(results[num_vms[0]]["slurm"]["exec-time"])

        num_slowdowns = 3
        percentiles = [50, 75, 90, 95, 100]
        width = float(1 / len(percentiles)) * 0.8
        xs = []
        ys = []
        xticks = []
        xlabels = []
        colors = []
        xs_vlines = []

        for vm_ind, n_vms in enumerate(num_vms):

            x_vm_offset = vm_ind * num_slowdowns

            # Calculate slowdowns wrt granny w/ migration
            slurm_slowdown = sorted(
                [
                    float(slurm_time / granny_time)
                    for (slurm_time, granny_time) in zip(
                        results[n_vms]["slurm"]["exec-time"],
                        results[n_vms]["granny-migrate"]["exec-time"],
                    )
                ]
            )
            batch_slowdown = sorted(
                [
                    float(batch_time / granny_time)
                    for (batch_time, granny_time) in zip(
                        results[n_vms]["batch"]["exec-time"],
                        results[n_vms]["granny-migrate"]["exec-time"],
                    )
                ]
            )
            granny_nomig_slowdown = sorted(
                [
                    float(granny_nomig_time / granny_time)
                    for (granny_nomig_time, granny_time) in zip(
                        results[n_vms]["granny"]["exec-time"],
                        results[n_vms]["granny-migrate"]["exec-time"],
                    )
                ]
            )

            for ind, (bline, slowdown) in enumerate(
                [
                    ("slurm", slurm_slowdown),
                    ("batch", batch_slowdown),
                    ("granny-no-migration", granny_nomig_slowdown),
                ]
            ):
                x_bline_offset = ind

                if "granny" in bline:
                    color = PLOT_COLORS["granny"]
                else:
                    color = PLOT_COLORS[bline]

                for subind, percentile in enumerate(percentiles):
                    x = (
                        x_vm_offset
                        + x_bline_offset
                        - width * int(len(percentiles) / 2)
                        + width * subind
                        + width * 0.5 * (len(percentiles) % 2 == 0)
                    )
                    xs.append(x)
                    if percentile == 100:
                        ys.append(slowdown[-1])
                    else:
                        index = int(percentile / 100 * num_jobs)
                        ys.append(slowdown[index])
                    colors.append(color)

            # Add a vertical line at the end of each VM block
            xs_vlines.append(
                x_vm_offset
                + (num_slowdowns * len(percentiles) + 1 - 0.25) * width
            )

            # Add a label once per VM block
            x_label = x_vm_offset + (
                (num_slowdowns * len(percentiles) + num_slowdowns - 2)
                / 2
                * width
            )
            xticks.append(x_label)
            xlabels.append(
                "{} VMs\n({} Jobs)".format(n_vms, num_tasks[vm_ind])
            )

        xmin = -0.5
        xmax = len(num_vms) * num_slowdowns - 0.5
        ymin = 0.75
        ymax = 2

        ax.bar(xs, ys, width=width, color=colors, edgecolor="black")
        ax.hlines(y=1, color="red", xmin=xmin, xmax=xmax)
        ax.vlines(
            xs_vlines,
            ymin=ymin,
            ymax=ymax,
            color="gray",
            linestyles="dashed",
            linewidth=0.5,
        )
        ax.set_xticks(xticks, labels=xlabels, fontsize=6)
        ax.set_ylabel("Slowdown [Baseline/Granny]")
        ax.set_xlabel(
            "Job percentile [{}]".format(
                ",".join([str(p) + "th" for p in percentiles])
            ),
            fontsize=8,
        )
        ax.set_xlim(left=xmin, right=xmax)
        ax.set_ylim(bottom=ymin, top=ymax)

    elif plot_name == "exec_abs":
        """
        TEMP
        """
        num_vms = 32
        num_jobs = len(results[num_vms]["slurm"]["exec-time"])
        labels = ["slurm", "batch", "granny", "granny-migrate"]
        percentiles = [50, 75, 90, 95, 100]

        xs = list(range(num_jobs))
        for label in labels:
            ys = []
            for percentile in percentiles:
                if percentile == 100:
                    index = -1
                else:
                    index = int(percentile / 100 * num_jobs)

                ys.append(results[num_vms][label]["exec-time"][index])

            this_label = label
            if label == "granny-migrate":
                this_label = "granny"
            elif label == "granny":
                this_label = "granny-nomig"

            ax.plot(
                percentiles, ys, label=this_label, color=PLOT_COLORS[label]
            )
            ax.set_xlabel("Job percentile [th]")
            ax.set_ylabel("Job completion time [s]")
            ax.set_ylim(bottom=0)
            ax.legend()

    elif plot_name == "exec_cdf":
        """
        CDF of the absolute job completion time
        (from the beginning of time, until the job has finished)
        """
        num_jobs = len(results[num_vms]["slurm"]["exec-time"])
        labels = ["slurm", "batch", "granny", "granny-migrate"]
        xs = list(range(num_jobs))

        for label in labels:
            ys = []

            this_label = label
            if label == "granny-migrate":
                this_label = "granny"
            elif label == "granny":
                this_label = "granny-nomig"

            # Calculate the histogram using the histogram function, get the
            # results from the return value, but make the plot transparent.
            # TODO: maybe just calculate the CDF analitically?
            ys, xs, patches = ax.hist(
                results[num_vms][label]["jct"],
                100,
                color=PLOT_COLORS[label],
                histtype="step",
                density=True,
                cumulative=True,
                label=this_label,
                # alpha=0,
            )
            fix_hist_step_vertical_line_at_end(ax)

            # Interpolate more points
            # spl = splrep(xs[:-1], ys, s=0.01, per=False)
            # x2 = linspace(xs[0], xs[-1], 400)
            # y2 = splev(x2, spl)
            # ax.plot(x2, y2, color=PLOT_COLORS[label], label=this_label, linewidth=0.5)

            ax.set_xlabel("Job Completion Time [s]")
            ax.set_ylabel("CDF")
            ax.set_ylim(bottom=0, top=1)
            ax.legend()

    elif plot_name == "makespan":
        labels = ["slurm", "batch", "granny", "granny-migrate"]

        xs = []
        ys = []
        colors = []
        xticks = []
        xticklabels = []

        # WARNING: this plot reads num_vms as an array
        for ind, n_vms in enumerate(num_vms):
            x_offset = ind * len(labels) + (ind + 1)
            xs += [x + x_offset for x in range(len(labels))]
            ys += [results[n_vms][la]["makespan"] for la in labels]
            colors += [PLOT_COLORS[la] for la in labels]

            # Add one tick and xlabel per VM size
            xticks.append(x_offset + len(labels) / 2)
            xticklabels.append(
                "{} VMs\n({} Jobs)".format(n_vms, num_tasks[ind])
            )

            # Add spacing between vms
            xs.append(x_offset + len(labels))
            ys.append(0)
            colors.append("white")

        ax.bar(xs, ys, color=colors, edgecolor="black", width=1)
        ax.set_ylim(bottom=0)
        ax.set_ylabel("Makespan [s]")
        ax.set_xticks(xticks, labels=xticklabels, fontsize=6)

        # Manually craft legend
        legend_entries = []
        for label in labels:
            if label == "granny":
                legend_entries.append(
                    Patch(color=PLOT_COLORS[label], label="granny-nomig")
                )
            elif label == "granny-migrate":
                legend_entries.append(
                    Patch(color=PLOT_COLORS[label], label="granny")
                )
            else:
                legend_entries.append(
                    Patch(color=PLOT_COLORS[label], label=label)
                )
        ax.legend(handles=legend_entries, ncols=2, fontsize=8)

    elif plot_name == "job_churn":
        """
        This plot presents a heatmap of the job churn for one execution of the
        trace. On the X axis we have time in seconds, and on the Y axis we have
        all vCPUs in the cluster (32 * 8). There are 100 different colors in
        the plot, one for each job. Coordinate [x, y] is of color C_j if Job
        `j` is using vCPU `y` at time `x`
        """
        # Fix one baseline (should we?)
        baseline = "slurm"
        # On the X axis, we have each job as a bar
        num_ts = len(results[baseline]["tasks_per_ts"])
        ncols = num_ts
        num_vms = 32
        num_cpus_per_vm = 8
        nrows = num_vms * num_cpus_per_vm

        # Data shape is (nrows, ncols). We have as many columns as tasks, and
        # as many rows as the total number of CPUs.
        # data[m, n] = task_id if cpu m is being used by task_id at timestamp n
        # (where  m is the row and n the column)
        data = [[-1 for _ in range(ncols)] for _ in range(nrows)]

        for ts in results[baseline]["tasks_per_ts"]:
            # This dictionary contains the in-flight tasks per timestamp (where
            # the timestamp has already been de-duplicated)
            tasks_in_flight = results[baseline]["tasks_per_ts"][ts]
            vm_cpu_offset = {}
            for i in range(num_vms):
                vm_cpu_offset[i] = 0
            for t in tasks_in_flight:
                t_id = int(t)
                sched_decision = results[baseline]["task_scheduling"][
                    str(t_id)
                ]
                # Work out which rows (i.e. CPU cores) to paint
                for vm in sched_decision:
                    cpus_in_vm = sched_decision[vm]
                    cpu_offset = vm_cpu_offset[vm]
                    vm_offset = vm * num_cpus_per_vm
                    this_offset = vm_offset + cpu_offset
                    for j in range(this_offset, this_offset + cpus_in_vm):
                        data[j][ts] = t_id
                    vm_cpu_offset[vm] += cpus_in_vm

        ax.imshow(data, origin="lower")

    elif plot_name == "ts_vcpus":
        """
        This plot presents a timeseries of the % of idle vCPUs over time
        """
        xs_slurm = range(len(results[num_vms]["slurm"]["ts_vcpus"]))
        xs_batch = range(len(results[num_vms]["batch"]["ts_vcpus"]))
        # xs_granny = list(results[num_vms]["granny"]["ts_vcpus"].keys())
        xs_granny_migrate = list(results[num_vms]["granny-migrate"]["ts_vcpus"].keys())

        ax.plot(
            xs_slurm,
            [results[num_vms]["slurm"]["ts_vcpus"][x] for x in xs_slurm],
            label="slurm",
            color=PLOT_COLORS["slurm"],
        )
        ax.plot(
            xs_batch,
            [results[num_vms]["batch"]["ts_vcpus"][x] for x in xs_batch],
            label="batch",
            color=PLOT_COLORS["batch"],
        )
        """
        ax.plot(
            xs_granny,
            [results[num_vms]["granny"]["ts_vcpus"][x] for x in xs_granny],
            label="granny",
            color=PLOT_COLORS["granny"],
        )
        """
        ax.plot(
            xs_granny_migrate,
            [
                results[num_vms]["granny-migrate"]["ts_vcpus"][x]
                for x in xs_granny_migrate
            ],
            label="granny-migrate",
            color=PLOT_COLORS["granny-migrate"],
        )

        xlim = max(
            xs_batch[-1],
            xs_slurm[-1],
            xs_granny_migrate[-1]
        )
        ax.set_xlim(left=0, right=xlim)
        ax.set_ylim(bottom=0, top=100)
        ax.set_ylabel("% idle vCPUs")
        ax.set_xlabel("Time [s]")

    elif plot_name == "ts_xvm_links":
        """
        This plot presents a timeseries of the # of cross-VM links over time
        """
        num_points = 500

        xs_slurm = range(len(results[num_vms]["slurm"]["ts_xvm_links"]))
        xs_batch = range(len(results[num_vms]["batch"]["ts_xvm_links"]))

        # xs_granny = list(results[num_vms]["granny"]["ts_xvm_links"].keys())
        # ys_granny = [results[num_vms]["granny"]["ts_xvm_links"][x] for x in xs_granny]
        # spl_granny = CubicSpline(xs_granny, ys_granny)
        # new_xs_granny = linspace(0, max(xs_granny), num=num_points)

        xs_granny_migrate = list(results[num_vms]["granny-migrate"]["ts_xvm_links"].keys())
        ys_granny_migrate = [results[num_vms]["granny-migrate"]["ts_xvm_links"][x] for x in xs_granny_migrate]
        spl_granny_migrate = CubicSpline(xs_granny_migrate, ys_granny_migrate)
        new_xs_granny_migrate = linspace(0, max(xs_granny_migrate), num=num_points)

        ax.plot(
            xs_slurm,
            [results[num_vms]["slurm"]["ts_xvm_links"][x] for x in xs_slurm],
            label="slurm",
            color=PLOT_COLORS["slurm"],
        )
        ax.plot(
            xs_batch,
            [results[num_vms]["batch"]["ts_xvm_links"][x] for x in xs_batch],
            label="batch",
            color=PLOT_COLORS["batch"],
        )
        """
        ax.plot(
            new_xs_granny,
            spl_granny(new_xs_granny),
            label="granny",
            color=PLOT_COLORS["granny"],
        )
        """
        ax.plot(
            new_xs_granny_migrate,
            spl_granny_migrate(new_xs_granny_migrate),
            label="granny-migrate",
            color=PLOT_COLORS["granny-migrate"],
        )

        xlim = max(
            xs_batch[-1],
            xs_slurm[-1],
            new_xs_granny_migrate[-1]
        )
        ax.set_xlim(left=0, right=xlim)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("# cross-VM links")
    elif plot_name == "ts_idle_vms":
        """
        This plot presents a timeseries of the # of idle VMs over time
        """
        num_points = 500

        xs_slurm = range(len(results[num_vms]["slurm"]["ts_xvm_links"]))
        xs_batch = range(len(results[num_vms]["batch"]["ts_xvm_links"]))

        # xs_granny = list(results[num_vms]["granny"]["ts_xvm_links"].keys())
        # ys_granny = [results[num_vms]["granny"]["ts_xvm_links"][x] for x in xs_granny]
        # spl_granny = CubicSpline(xs_granny, ys_granny)
        # new_xs_granny = linspace(0, max(xs_granny), num=num_points)

        # TODO: FIXME: move from granny-migrate to granny-evict!
        xs_granny_migrate = list(results[num_vms]["granny-migrate"]["ts_idle_vms"].keys())
        ys_granny_migrate = [(results[num_vms]["granny-migrate"]["ts_idle_vms"][x] / num_vms) * 100 for x in xs_granny_migrate]
        spl_granny_migrate = CubicSpline(xs_granny_migrate, ys_granny_migrate)
        new_xs_granny_migrate = linspace(0, max(xs_granny_migrate), num=num_points)

        ax.plot(
            xs_slurm,
            [(results[num_vms]["slurm"]["ts_idle_vms"][x] / num_vms) * 100 for x in xs_slurm],
            label="slurm",
            color=PLOT_COLORS["slurm"],
        )
        ax.plot(
            xs_batch,
            [(results[num_vms]["batch"]["ts_idle_vms"][x] / num_vms) * 100 for x in xs_batch],
            label="batch",
            color=PLOT_COLORS["batch"],
        )
        """
        ax.plot(
            new_xs_granny,
            spl_granny(new_xs_granny),
            label="granny",
            color=PLOT_COLORS["granny"],
        )
        """
        # TODO: FIXME move to granny-evict
        ax.plot(
            new_xs_granny_migrate,
            spl_granny_migrate(new_xs_granny_migrate),
            label="granny-migrate",
            color=PLOT_COLORS["granny-migrate"],
        )

        xlim = max(
            xs_batch[-1],
            xs_slurm[-1],
            new_xs_granny_migrate[-1]
        )
        ax.set_xlim(left=0, right=xlim)
        ax.set_ylim(bottom=0, top=100)
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Idle VMs [%]")
    elif plot_name == "boxplot_vcpus":
        labels = ["slurm", "batch", "granny", "granny-migrate"]

        xs = []
        ys = []
        colors = []
        alphas = []
        xticks = []
        xticklabels = []

        num_cpus_per_vm = 8

        # Integral of idle CPU cores over time
        # WARNING: this plot reads num_vms as an array
        cumsum_ys = {}
        for la in labels:
            cumsum_ys[la] = {}

            for n_vms in num_vms:
                timestamps = list(results[n_vms][la]["ts_vcpus"].keys())
                total_cpusecs = (timestamps[-1] - timestamps[0]) * num_cpus_per_vm * int(n_vms)

                cumsum = cum_sum(
                    timestamps,
                    [res * num_cpus_per_vm * int(n_vms) / 100 for res in list(results[n_vms][la]["ts_vcpus"].values())],
                )

                # Record both the total idle CPUsecs and the percentage
                cumsum_ys[la][n_vms] = (cumsum, (cumsum / total_cpusecs) * 100)

        xs = [ind for ind in range(len(num_vms))]
        xticklabels = []

        for (n_vms, n_tasks) in zip(num_vms, num_tasks):
            xticklabels.append(
                "{} VMs\n({} Jobs)".format(n_vms, n_tasks)
            )
        for la in labels:
            ys = [cumsum_ys[la][n_vms][1] for n_vms in num_vms]
            ax.plot(
                xs,
                ys,
                color=PLOT_COLORS[la],
                linestyle="-",
                marker=".",
                label=la,
            )

        ax.set_ylim(bottom=0)
        ax.set_xlim(left=-0.25)
        ax.set_ylabel("Idle CPU-seconds /\n Total CPU-seconds [%]", fontsize=8)
        ax.set_xticks(xs, labels=xticklabels, fontsize=6)
        ax.legend(fontsize=6, ncols=2)

    elif plot_name == "percentage_xvm":
        labels = ["slurm", "batch", "granny", "granny-migrate"]

        xs = []
        ys = []
        colors = []
        xticks = []
        xticklabels = []

        num_cpus_per_vm = 8

        # Integral of idle CPU cores over time
        cumsum_ys = {}
        for la in labels:
            cumsum_ys[la] = {}

            for n_vms in num_vms:
                timestamps = list(results[n_vms][la]["ts_xvm_links"].keys())
                total_cpusecs = (timestamps[-1] - timestamps[0]) * num_cpus_per_vm * int(n_vms)

                cumsum = cum_sum(
                    timestamps,
                    [res for res in list(results[n_vms][la]["ts_xvm_links"].values())],
                )

                cumsum_ys[la][n_vms] = cumsum

        # WARNING: this plot reads num_vms as an array
        xs = [ind for ind in range(len(num_vms))]
        xticklabels = []
        for (n_vms, n_tasks) in zip(num_vms, num_tasks):
            xticklabels.append(
                "{} VMs\n({} Jobs)".format(n_vms, n_tasks)
            )
        for la in labels:
            ys = [cumsum_ys[la][n_vms] / cumsum_ys["batch"][n_vms] for n_vms in num_vms]
            ax.plot(
                xs,
                ys,
                color=PLOT_COLORS[la],
                linestyle="-",
                marker=".",
                label=la,
            )

        ax.set_ylim(bottom=0)
        ax.set_xlim(left=-0.25)
        ax.set_ylabel("Total cross-VM / Optimal cross-VM links", fontsize=8)
        ax.set_xticks(xs, labels=xticklabels, fontsize=6)
        # ax.ticklabel_format(axis="y", style="sci", scilimits=(5, 5))
        ax.legend(fontsize=6, ncols=2)

    # TODO: delete me
    elif plot_name == "boxplot_xvm":
        labels = ["slurm", "batch", "granny", "granny-migrate"]

        xs = []
        ys = []
        colors = []
        xticks = []
        xticklabels = []

        # WARNING: this plot reads num_vms as an array
        for ind, n_vms in enumerate(num_vms):
            x_offset = ind * len(labels) + (ind + 1)

            # For each cluster size, and for each label, we add two boxplots

            # Number of cross-VM links
            xs += [x + x_offset for x in range(len(labels))]
            ys += [list(results[n_vms][la]["ts_xvm_links"].values()) for la in labels]

            # Color and alpha for each box
            colors += [PLOT_COLORS[la] for la in labels]

            # Add one tick and xlabel per VM size
            xticks.append(x_offset + len(labels) / 2)
            xticklabels.append(
                "{} VMs\n({} Jobs)".format(n_vms, num_tasks[ind])
            )

        bplot = ax.boxplot(
            ys,
            sym="",
            vert=True,
            positions=xs,
            patch_artist=True,
            widths=0.5,
        )

        for (box, color) in zip(bplot['boxes'], colors):
            box.set_facecolor(color)
            box.set_edgecolor("black")

        ax.set_ylim(bottom=0)
        ax.set_ylabel("# cross-VM links")
        ax.set_xticks(xticks, labels=xticklabels, fontsize=6)

        # Manually craft legend
        legend_entries = []
        for label in labels:
            if label == "granny":
                legend_entries.append(
                    Patch(color=PLOT_COLORS[label], label="granny-nomig")
                )
            elif label == "granny-migrate":
                legend_entries.append(
                    Patch(color=PLOT_COLORS[label], label="granny")
                )
            else:
                legend_entries.append(
                    Patch(color=PLOT_COLORS[label], label=label)
                )
        ax.legend(handles=legend_entries, ncols=2, fontsize=8)
    elif plot_name == "used_vmsecs":
        # TODO: FIXME: move to granny-evict
        labels = ["slurm", "batch", "granny", "granny-migrate"]

        xs = []
        ys = []
        colors = []
        xticks = []
        xticklabels = []

        # Integral of idle CPU cores over time
        cumsum_ys = {}
        for la in labels:
            cumsum_ys[la] = {}

            for n_vms in num_vms:
                timestamps = list(results[n_vms][la]["ts_idle_vms"].keys())
                # total_cpusecs = (timestamps[-1] - timestamps[0]) * num_cpus_per_vm * int(n_vms)

                cumsum = cum_sum(
                    timestamps,
                    [(n_vms - res) for res in list(results[n_vms][la]["ts_idle_vms"].values())],
                )
                # TODO: delete me
                if n_vms == 16:
                    print(n_vms, la, cumsum, [res for res in list(results[n_vms][la]["ts_idle_vms"].values())])

                cumsum_ys[la][n_vms] = cumsum

        # WARNING: this plot reads num_vms as an array
        xs = [ind for ind in range(len(num_vms))]
        xticklabels = []
        for (n_vms, n_tasks) in zip(num_vms, num_tasks):
            xticklabels.append(
                "{} VMs\n({} Jobs)".format(n_vms, n_tasks)
            )
        for la in labels:
            ys = [cumsum_ys[la][n_vms] for n_vms in num_vms]
            ax.plot(
                xs,
                ys,
                color=PLOT_COLORS[la],
                linestyle="-",
                marker=".",
                label=la,
            )

        ax.set_ylim(bottom=0)
        ax.set_xlim(left=-0.25)
        ax.set_ylabel("Used VM Seconds", fontsize=8)
        ax.set_xticks(xs, labels=xticklabels, fontsize=6)
        ax.ticklabel_format(axis="y", style="sci", scilimits=(3, 3))
        ax.legend(fontsize=6, ncols=2)
