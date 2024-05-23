from glob import glob
from numpy import linspace
from os.path import join
from pandas import read_csv
from scipy.interpolate import CubicSpline
from tasks.util.makespan import (
    GRANNY_BASELINES,
    MAKESPAN_RESULTS_DIR,
    NATIVE_BASELINES,
)
from tasks.util.math import cum_sum
from tasks.util.planner import get_xvm_links_from_part
from tasks.util.plot import (
    fix_hist_step_vertical_line_at_end,
    get_color_for_baseline,
    get_label_for_baseline,
)
from tasks.util.trace import load_task_trace_from_file

# ----------------------------
# Plotting utilities
# ----------------------------


def read_locality_results(num_vms, num_tasks, num_cpus_per_vm, migrate=False):
    workload = "mpi-locality" if not migrate else "mpi-migrate"

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
            with open(
                join(MAKESPAN_RESULTS_DIR, sched_info_csv), "r"
            ) as sched_fd:
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
                    for vm_id in result_dict[baseline]["task_scheduling"][
                        str(int(t))
                    ]:
                        result_dict[baseline]["ts_idle_vms"][ts].add(vm_id)

            # Third, express the results as percentages, and the number of
            # idle VMs as a number (not as a set)
            for ts in result_dict[baseline]["ts_vcpus"]:
                result_dict[baseline]["ts_vcpus"][ts] = (
                    result_dict[baseline]["ts_vcpus"][ts]
                    / total_available_vcpus
                ) * 100

                result_dict[baseline]["ts_idle_vms"][ts] = num_vms - len(
                    result_dict[baseline]["ts_idle_vms"][ts]
                )
        else:
            # For Granny, the idle vCPUs results are directly available in
            # the file
            sch_info_csv = read_csv(join(MAKESPAN_RESULTS_DIR, sched_info_csv))
            idle_cpus = (
                sch_info_csv["NumIdleCpus"] / total_available_vcpus * 100
            ).to_list()
            tss = (
                sch_info_csv["TimeStampSecs"]
                - sch_info_csv["TimeStampSecs"][0]
            ).to_list()

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
                        result_dict[baseline]["ts_xvm_links"][
                            ts
                        ] += get_xvm_links_from_part(list(sched.values()))
                    elif baseline == "batch":
                        # Batch baseline is optimal in terms of cross-vm links
                        task_size = task_trace[int(t)].size
                        if task_size > 8:
                            num_links = 8 * (task_size - 8) / 2
                            result_dict[baseline]["ts_xvm_links"][
                                ts
                            ] += num_links

    return result_dict


def _do_plot_exec_vs_tiq(results, ax, **kwargs):
    """
    This plot presents the percentiles of slowdown of execution time (and
    time in queue too?)
    """
    num_vms = kwargs["num_vms"]
    num_tasks = kwargs["num_tasks"]

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
                colors.append(get_color_for_baseline("mpi-migrate", bline))

        # Add a vertical line at the end of each VM block
        xs_vlines.append(
            x_vm_offset + (num_slowdowns * len(percentiles) + 1 - 0.25) * width
        )

        # Add a label once per VM block
        x_label = x_vm_offset + (
            (num_slowdowns * len(percentiles) + num_slowdowns - 2) / 2 * width
        )
        xticks.append(x_label)
        xlabels.append("{} VMs\n({} Jobs)".format(n_vms, num_tasks[vm_ind]))

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


def _do_plot_exec_cdf(results, ax, **kwargs):
    """
    CDF of the absolute job completion time
    (from the beginning of time, until the job has finished)
    """
    num_vms = kwargs["num_vms"]

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
            color=get_color_for_baseline("mpi-migrate", label),
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


def _do_plot_makespan(results, ax, **kwargs):
    num_vms = kwargs["num_vms"]
    num_tasks = kwargs["num_tasks"]
    baselines = ["granny", "granny-batch", "granny-migrate"]

    xs = []
    ys = []
    colors = []
    xticks = []
    xticklabels = []

    for ind, n_vms in enumerate(num_vms):
        x_offset = ind * len(baselines) + (ind + 1)
        xs += [x + x_offset for x in range(len(baselines))]
        ys += [results[n_vms][la]["makespan"] for la in baselines]
        colors += [
            get_color_for_baseline("mpi-locality", la) for la in baselines
        ]

        # Add one tick and xlabel per VM size
        xticks.append(x_offset + len(baselines) / 2)
        xticklabels.append("{} VMs\n({} Jobs)".format(n_vms, num_tasks[ind]))

        # Add spacing between vms
        xs.append(x_offset + len(baselines))
        ys.append(0)
        colors.append("white")

    ax.bar(xs, ys, color=colors, edgecolor="black", width=1)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Makespan [s]")
    ax.set_xticks(xticks, labels=xticklabels)


def _do_plot_ts_vcpus(results, ax, **kwargs):
    """
    This plot presents a timeseries of the % of idle vCPUs over time
    """
    num_vms = kwargs["num_vms"]
    workload = "mpi-migrate" if "migrate" in kwargs else "mpi-locality"

    if workload == "mpi-migrate":
        baselines = ["batch", "slurm", "granny", "granny-migrate"]
    else:
        baselines = ["granny", "granny-batch", "granny-migrate"]

    xlim = 0
    for baseline in baselines:
        if baseline in NATIVE_BASELINES:
            xs = range(len(results[num_vms][baseline]["ts_vcpus"]))
        else:
            xs = list(results[num_vms][baseline]["ts_vcpus"].keys())
        xlim = max(xlim, max(xs))

        ax.plot(
            xs,
            [results[num_vms][baseline]["ts_vcpus"][x] for x in xs],
            label=get_label_for_baseline(workload, baseline),
            color=get_color_for_baseline(workload, baseline),
        )

    ax.set_xlim(left=0, right=xlim)
    ax.set_ylim(bottom=0, top=100)
    ax.set_ylabel("% idle vCPUs")
    ax.set_xlabel("Time [s]")


def _do_plot_ts_xvm_links(results, ax, **kwargs):
    """
    This plot presents a timeseries of the # of cross-VM links over time
    """
    num_vms = kwargs["num_vms"]
    workload = "mpi-migrate" if "migrate" in kwargs else "mpi-locality"
    num_points = 500

    if workload == "mpi-migrate":
        baselines = ["batch", "slurm"]
    else:
        baselines = ["granny", "granny-batch"]

    xlim = 0
    for baseline in baselines:
        if workload == "mpi-migrate":
            xs = range(len(results[num_vms][baseline]["ts_xvm_links"]))
        else:
            xs = list(results[num_vms][baseline]["ts_xvm_links"].keys())
        xlim = max(xlim, max(xs))

        ax.plot(
            xs,
            [results[num_vms][baseline]["ts_xvm_links"][x] for x in xs],
            label=get_label_for_baseline(workload, baseline),
            color=get_color_for_baseline(workload, baseline),
        )

    # We do Granny separately to interpolate
    xs_granny_migrate = list(
        results[num_vms]["granny-migrate"]["ts_xvm_links"].keys()
    )
    ys_granny_migrate = [
        results[num_vms]["granny-migrate"]["ts_xvm_links"][x]
        for x in xs_granny_migrate
    ]
    spl_granny_migrate = CubicSpline(xs_granny_migrate, ys_granny_migrate)
    new_xs_granny_migrate = linspace(0, max(xs_granny_migrate), num=num_points)

    ax.plot(
        new_xs_granny_migrate,
        spl_granny_migrate(new_xs_granny_migrate),
        label=get_label_for_baseline(workload, "granny-migrate"),
        color=get_color_for_baseline(workload, "granny-migrate"),
    )

    xlim = max(xlim, max(new_xs_granny_migrate))
    ax.set_xlim(left=0, right=xlim)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("# cross-VM links")


def _do_plot_percentage_vcpus(results, ax, **kwargs):
    num_vms = kwargs["num_vms"]
    workload = "mpi-migrate" if "migrate" in kwargs else "mpi-locality"
    num_tasks = kwargs["num_tasks"]

    if workload == "mpi-migrate":
        baselines = ["batch", "slurm", "granny", "granny-migrate"]
    else:
        baselines = ["granny", "granny-batch", "granny-migrate"]

    xs = []
    ys = []
    xticklabels = []

    num_cpus_per_vm = 8

    # Integral of idle CPU cores over time
    # WARNING: this plot reads num_vms as an array
    cumsum_ys = {}
    for baseline in baselines:
        cumsum_ys[baseline] = {}

        for n_vms in num_vms:
            timestamps = list(results[n_vms][baseline]["ts_vcpus"].keys())
            total_cpusecs = (
                (timestamps[-1] - timestamps[0]) * num_cpus_per_vm * int(n_vms)
            )

            cumsum = cum_sum(
                timestamps,
                [
                    res * num_cpus_per_vm * int(n_vms) / 100
                    for res in list(
                        results[n_vms][baseline]["ts_vcpus"].values()
                    )
                ],
            )

            # Record both the total idle CPUsecs and the percentage
            cumsum_ys[baseline][n_vms] = (
                cumsum,
                (cumsum / total_cpusecs) * 100,
            )

    xs = [ind for ind in range(len(num_vms))]
    xticklabels = []

    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        xticklabels.append("{} VMs\n({} Jobs)".format(n_vms, n_tasks))
    for baseline in baselines:
        ys = [cumsum_ys[baseline][n_vms][1] for n_vms in num_vms]
        ax.plot(
            xs,
            ys,
            color=get_color_for_baseline(workload, baseline),
            linestyle="-",
            marker=".",
            label=get_label_for_baseline(workload, baseline),
        )

    ax.set_ylim(bottom=0)
    ax.set_xlim(left=-0.25)
    ax.set_ylabel("Idle CPU-seconds /\n Total CPU-seconds [%]", fontsize=8)
    ax.set_xticks(xs, labels=xticklabels)


def _do_plot_percentage_xvm(results, ax, **kwargs):
    num_vms = kwargs["num_vms"]
    workload = "mpi-migrate" if "migrate" in kwargs else "mpi-locality"
    num_tasks = kwargs["num_tasks"]

    if workload == "mpi-migrate":
        baselines = ["batch", "slurm", "granny", "granny-migrate"]
        optimal_baseline = "batch"
    else:
        baselines = ["granny", "granny-batch", "granny-migrate"]
        optimal_baseline = "granny-batch"

    xs = []
    ys = []
    xticklabels = []

    # Integral of idle CPU cores over time
    cumsum_ys = {}
    for baseline in baselines:
        cumsum_ys[baseline] = {}

        for n_vms in num_vms:
            timestamps = list(results[n_vms][baseline]["ts_xvm_links"].keys())

            cumsum = cum_sum(
                timestamps,
                [
                    res
                    for res in list(
                        results[n_vms][baseline]["ts_xvm_links"].values()
                    )
                ],
            )

            cumsum_ys[baseline][n_vms] = cumsum

    # WARNING: this plot reads num_vms as an array
    xs = [ind for ind in range(len(num_vms))]
    xticklabels = []
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        xticklabels.append("{} VMs\n({} Jobs)".format(n_vms, n_tasks))
    for baseline in baselines:
        ys = [
            cumsum_ys[baseline][n_vms] / cumsum_ys[optimal_baseline][n_vms]
            for n_vms in num_vms
        ]
        ax.plot(
            xs,
            ys,
            label=get_label_for_baseline(workload, baseline),
            color=get_color_for_baseline(workload, baseline),
            linestyle="-",
            marker=".",
        )

    ax.set_ylim(bottom=0)
    ax.set_xlim(left=-0.25)
    ax.set_ylabel("Total cross-VM / Optimal cross-VM links", fontsize=8)
    ax.set_xticks(xs, labels=xticklabels)


def _do_plot_cdf_jct(results, ax, **kwargs):
    assert "cdf_num_vms" in kwargs, "cdf_num_vms not in kwargs!"
    assert "cdf_num_tasks" in kwargs, "cdf_num_tasks not in kwargs!"
    cdf_num_vms = kwargs["cdf_num_vms"]
    cdf_num_tasks = kwargs["cdf_num_tasks"]

    baselines = ["granny-batch", "granny", "granny-migrate"]

    xs = list(range(cdf_num_tasks))
    for baseline in baselines:
        ys = []

        ys, xs, patches = ax.hist(
            results[cdf_num_vms][baseline]["jct"],
            100,
            color=get_color_for_baseline("mpi-locality", baseline),
            label=get_label_for_baseline("mpi-locality", baseline),
            histtype="step",
            density=True,
            cumulative=True,
        )
        fix_hist_step_vertical_line_at_end(ax)

        ax.set_xlabel("Job Completion Time [s]")
        ax.set_ylabel("CDF")
        ax.set_ylim(bottom=0, top=1)


def plot_locality_results(plot_name, results, ax, **kwargs):
    """
    This method keeps track of all the different alternative plots we have
    explored for the motivation figure.
    """
    if plot_name == "exec_vs_tiq":
        _do_plot_exec_vs_tiq(results, ax, **kwargs)
    elif plot_name == "exec_cdf":
        _do_plot_exec_cdf(results, ax, **kwargs)
    elif plot_name == "makespan":
        _do_plot_makespan(results, ax, **kwargs)
    elif plot_name == "ts_vcpus":
        _do_plot_ts_vcpus(results, ax, **kwargs)
    elif plot_name == "ts_xvm_links":
        _do_plot_ts_xvm_links(results, ax, **kwargs)
    elif plot_name == "percentage_vcpus":
        _do_plot_percentage_vcpus(results, ax, **kwargs)
    elif plot_name == "percentage_xvm":
        _do_plot_percentage_xvm(results, ax, **kwargs)
    elif plot_name == "cdf_jct":
        _do_plot_cdf_jct(results, ax, **kwargs)
