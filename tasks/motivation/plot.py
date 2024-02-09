from glob import glob
from invoke import task
from matplotlib.patches import Patch, Polygon

# from numpy import linspace
from os import makedirs
from os.path import join

# from scipy.interpolate import splev, splrep
from tasks.makespan.trace import load_task_trace_from_file
from tasks.makespan.util import GRANNY_BASELINES
from tasks.util.env import PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT
from tasks.util.plot import PLOT_COLORS

import matplotlib.pyplot as plt
import pandas as pd

RESULTS_DIR = join(PROJ_ROOT, "results", "makespan")
PLOTS_DIR = join(PLOTS_ROOT, "makespan")
OUT_FILE_TIQ = join(PLOTS_DIR, "time_in_queue.{}".format(PLOTS_FORMAT))
WORKLOAD_TO_LABEL = {
    "wasm": "Granny",
    "batch": "Batch (1 usr)",
    "batch2": "Batch (2 usr)",
}


def fix_hist_step_vertical_line_at_end(ax):
    axpolygons = [
        poly for poly in ax.get_children() if isinstance(poly, Polygon)
    ]
    for poly in axpolygons:
        poly.set_xy(poly.get_xy()[:-1])


def do_read_results(num_vms, num_tasks, num_cpus_per_vm):
    workload = "mpi-migrate"

    # Load results
    result_dict = {}
    glob_str = "makespan_exec-task-info_*_{}_{}_{}_{}.csv".format(
        num_vms, workload, num_tasks, num_cpus_per_vm
    )
    for csv in glob(join(RESULTS_DIR, glob_str)):
        baseline = csv.split("_")[2]
        workload = csv.split("_")[4]

        # -----
        # Results to visualise differences between execution time and time
        # in queue
        # -----

        # Results for per-job exec time and time-in-queue
        result_dict[baseline] = {}
        results = pd.read_csv(csv)
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

        if baseline not in GRANNY_BASELINES:
            result_dict[baseline]["task_scheduling"] = {}

            # We identify VMs by numbers, not IPs
            ip_to_vm = {}
            vm_to_id = {}
            sched_info_csv = "makespan_sched-info_{}_{}_{}_{}_{}.csv".format(
                baseline, num_vms, workload, num_tasks, num_cpus_per_vm
            )
            with open(join(RESULTS_DIR, sched_info_csv), "r") as sched_fd:
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
        # Results to visualise the % of idle vCPUs over time
        # -----

        task_trace = load_task_trace_from_file(
            workload, num_tasks, num_cpus_per_vm
        )

        # First, set each timestamp to the total available vCPUs
        total_available_vcpus = num_vms * num_cpus_per_vm
        result_dict[baseline]["ts_vcpus"] = {}
        for ts in result_dict[baseline]["tasks_per_ts"]:
            result_dict[baseline]["ts_vcpus"][ts] = total_available_vcpus

        # Second, for each ts subtract the size of each task in-flight
        for ts in result_dict[baseline]["tasks_per_ts"]:
            for t in result_dict[baseline]["tasks_per_ts"][ts]:
                result_dict[baseline]["ts_vcpus"][ts] -= task_trace[
                    int(t)
                ].size

        # Third, express the results as percentages
        for ts in result_dict[baseline]["ts_vcpus"]:
            result_dict[baseline]["ts_vcpus"][ts] = (
                result_dict[baseline]["ts_vcpus"][ts] / total_available_vcpus
            ) * 100

        # -----
        # Results to visualise the # of cross-vm links
        # -----

        if baseline != "granny":
            result_dict[baseline]["ts_xvm_links"] = {}
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

                        # Otherwise, make the product
                        acc = 1
                        for vm in sched:
                            acc = acc * sched[vm]

                        # Add the accumulated to the total tally
                        result_dict[baseline]["ts_xvm_links"][ts] += acc
                    elif baseline == "batch":
                        # Batch baseline is optimal in terms of cross-vm links
                        task_size = task_trace[int(t)].size
                        if task_size > 8:
                            num_links = 8 * (task_size - 8)
                            result_dict[baseline]["ts_xvm_links"][
                                ts
                            ] += num_links

    return result_dict


def do_plot(plot_name, results, ax, num_vms, num_tasks):
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
        num_vms = 32
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
        xs_slurm = range(len(results["slurm"]["ts_vcpus"]))
        xs_batch = range(len(results["batch"]["ts_vcpus"]))
        xs_granny = range(len(results["granny"]["ts_vcpus"]))
        xs_granny_migrate = range(len(results["granny-migrate"]["ts_vcpus"]))

        ax.plot(
            xs_slurm,
            [results["slurm"]["ts_vcpus"][x] for x in xs_slurm],
            label="slurm",
            color=PLOT_COLORS["slurm"],
        )
        ax.plot(
            xs_batch,
            [results["batch"]["ts_vcpus"][x] for x in xs_batch],
            label="batch",
            color=PLOT_COLORS["batch"],
        )
        ax.plot(
            xs_granny,
            [results["granny"]["ts_vcpus"][x] for x in xs_granny],
            label="granny",
            color=PLOT_COLORS["granny"],
        )
        ax.plot(
            xs_granny_migrate,
            [
                results["granny-migrate"]["ts_vcpus"][x]
                for x in xs_granny_migrate
            ],
            label="granny-migrate",
            color=PLOT_COLORS["granny-migrate"],
        )
        ax.set_xlim(left=0)  # , right=400)
        ax.set_ylim(bottom=0, top=100)
        ax.set_ylabel("% idle vCPUs")
        ax.set_xlabel("Time [s]")
        # ax.legend(ncol=4, bbox_to_anchor=(0.95, 1.25))

    elif plot_name == "ts_xvm_links":
        """
        This plot presents a timeseries of the # of cross-VM links over time
        """
        xs_slurm = range(len(results["slurm"]["ts_xvm_links"]))
        xs_batch = range(len(results["batch"]["ts_xvm_links"]))

        ax.plot(
            xs_slurm,
            [results["slurm"]["ts_xvm_links"][x] for x in xs_slurm],
            label="slurm",
            color="orange",
        )
        ax.plot(
            xs_batch,
            [results["batch"]["ts_xvm_links"][x] for x in xs_batch],
            label="batch",
            color="blue",
        )
        ax.set_xlim(left=0, right=400)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("# cross-VM links")
        # ax.legend()


@task(default=True)
def plot(ctx):
    """
    Motivation plot:
    - Baselines: `slurm` and `batch`
    - TOP: timeseries of % of idle vCPUs over time
    - BOTTOM: timeseries of # of cross-VM links over time
    """
    num_vms = [16, 24, 32, 48, 64]
    num_tasks = [50, 75, 100, 150, 200]
    num_cpus_per_vm = 8

    plots_dir = join(PLOTS_ROOT, "motivation")
    makedirs(plots_dir, exist_ok=True)

    # Read results from files
    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = do_read_results(n_vms, n_tasks, num_cpus_per_vm)

    fig, (ax1, ax2) = plt.subplots(nrows=1, ncols=2)  # , figsize=(6, 3))
    fig.subplots_adjust(wspace=0.35)

    # TODO: check result integrity

    # ----------
    # Plot 1: TODO
    # ----------

    # do_plot("exec_vs_tiq", results, ax1, num_vms, num_tasks)
    do_plot("exec_cdf", results, ax1, num_vms, num_tasks)

    # ----------
    # Plot 2: Job Churn
    # ----------

    do_plot("makespan", results, ax2, num_vms, num_tasks)

    # ----------
    # Save figure
    # ----------

    out_file = join(plots_dir, "motivation.{}".format(PLOTS_FORMAT))
    plt.savefig(out_file, format=PLOTS_FORMAT, bbox_inches="tight")
