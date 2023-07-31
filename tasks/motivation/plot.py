from glob import glob
from invoke import task
from os import makedirs
from os.path import join
from tasks.makespan.trace import load_task_trace_from_file
from tasks.makespan.util import get_trace_from_parameters
from tasks.util.env import PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

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


def _read_results():
    # TODO: decide
    # workload = "mpi-migrate"
    workload = "mpi"

    # Load results
    result_dict = {}
    trace = get_trace_from_parameters(workload, 100, 8)
    trace_ending = trace[6:]
    glob_str = "makespan_exec-task-info_*_{}_{}_{}".format(
        "k8s", 32, trace_ending
    )
    for csv in glob(join(RESULTS_DIR, glob_str)):
        baseline = csv.split("_")[2]

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
        result_dict[baseline]["exec-time"] = [-1 for _ in task_ids]
        result_dict[baseline]["queue-time"] = [-1 for _ in task_ids]

        for tid, texec, tqueue in zip(task_ids, times_exec, times_queue):
            result_dict[baseline]["exec-time"][tid] = texec
            result_dict[baseline]["queue-time"][tid] = tqueue

        # -----
        # Results to visualise job churn
        # -----

        start_ts = results.min()["StartTimeStamp"]
        end_ts = results.max()["EndTimeStamp"]
        time_elapsed_secs = int(end_ts - start_ts)
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

        if baseline != "granny":
            result_dict[baseline]["task_scheduling"] = {}

            # We identify VMs by numbers, not IPs
            ip_to_vm = {}
            vm_to_id = {}
            sched_info_csv = "makespan_sched-info_{}_{}_{}_{}".format(
                csv.split("_")[2], "k8s", "32", trace_ending
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

        task_trace = load_task_trace_from_file("mpi", 100, 8)

        # First, set each timestamp to the total available vCPUs
        total_available_vcpus = 32 * 8
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
                            result_dict[baseline]["ts_xvm_links"][ts] += num_links

    return result_dict


def do_plot(plot_name, results, ax):
    """
    This method keeps track of all the different alternative plots we have
    explored for the motivation figure.
    """

    if plot_name == "exec_vs_tiq":
        """
        This plot compares the execution time and the time in queue for all
        jobs in a trace. In the X axis we have the job number, and on the Y
        axis both the executin time and the time in queue.
        """
        num_jobs = len(results["slurm"]["exec-time"])
        x1 = range(num_jobs)

        ax.plot(
            x1, results["slurm"]["exec-time"], label="slurm", color="orange"
        )
        ax.plot(x1, results["batch"]["exec-time"], label="batch", color="blue")
        ax.plot(
            x1,
            results["slurm"]["queue-time"],
            color="orange",
            linestyle="dashed",
        )
        ax.plot(
            x1,
            results["batch"]["queue-time"],
            color="blue",
            linestyle="dashed",
        )
        ax.legend()

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

        ax.plot(
            xs_slurm,
            [results["slurm"]["ts_vcpus"][x] for x in xs_slurm],
            label="slurm",
            color="orange",
        )
        ax.plot(
            xs_batch,
            [results["batch"]["ts_vcpus"][x] for x in xs_batch],
            label="batch",
            color="blue",
        )
        ax.plot(
            xs_granny,
            [results["granny"]["ts_vcpus"][x] for x in xs_granny],
            label="granny",
            color="red",
        )
        ax.set_xlim(left=0, right=400)
        ax.set_ylim(bottom=0, top=100)
        ax.set_ylabel("% idle vCPUs")
        ax.legend(ncol=3)

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
    - RHS: timeseries of # of cross-VM links over time
    """
    plots_dir = join(PLOTS_ROOT, "motivation")
    makedirs(plots_dir, exist_ok=True)

    results = _read_results()
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True, figsize=(6, 3))
    fig.subplots_adjust(hspace=0)

    # TODO: check result integrity

    # ----------
    # Plot 1: TODO
    # ----------

    do_plot("ts_vcpus", results, ax1)

    # ----------
    # Plot 2: Job Churn
    # ----------

    do_plot("ts_xvm_links", results, ax2)

    # ----------
    # Save figure
    # ----------

    out_file = join(plots_dir, "motivation.{}".format(PLOTS_FORMAT))
    plt.savefig(out_file, format=PLOTS_FORMAT, bbox_inches="tight")
