from glob import glob
from invoke import task
from numpy import arange
from os import makedirs
from os.path import join
from tasks.makespan.util import (
    get_num_cores_from_trace,
    get_trace_ending,
    get_trace_from_parameters,
)
from tasks.util.env import MPL_STYLE_FILE, PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT
from tasks.util.plot import PLOT_COLORS, PLOT_LABELS, PLOT_PATTERNS

import matplotlib.patches as mpatches
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
    baseline_map = {"native-8": "slurm", "native-1": "batch"}

    # Load results
    result_dict = {}
    trace = get_trace_from_parameters(workload, 100, 8)
    trace_ending = trace[6:]
    glob_str = "makespan_exec-task-info_*_{}_{}_{}".format("k8s", 32, trace_ending)
    for csv in glob(join(RESULTS_DIR, glob_str)):
        # Filter-out baselines
        baseline = csv.split("_")[2]
        if baseline not in baseline_map:
            continue
        baseline = baseline_map[baseline]

        # Results for per-job exec time and time-in-queue
        result_dict[baseline] = {}
        results = pd.read_csv(csv)
        task_ids = results[
            "TaskId"
        ].to_list()
        times_exec = results[
            "TimeExecuting"
        ].to_list()
        times_queue = results[
                "TimeInQueue"
        ].to_list()
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
        prev_tasks = []
        for ts, tasks in enumerate(tasks_per_ts):
            if tasks != prev_tasks:
                pruned_tasks_per_ts[ts] = tasks
            prev_tasks = tasks

        result_dict[baseline]["tasks_per_ts"] = pruned_tasks_per_ts

    return result_dict


@task(default=True)
def plot(ctx):
    """
    Motivation plot:
    - Baselines: `slurm` and `batch`
    - LHS: per-job comparison of the time in queue and execution time
    - RHS: tbd
    """
    plots_dir = join(PLOTS_ROOT, "motivation")
    makedirs(plots_dir, exist_ok=True)

    results = _read_results()
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1)

    # TODO: check result integrity

    num_jobs = len(results["slurm"]["exec-time"])
    x1 = range(num_jobs)
    ax1.plot(x1, results["slurm"]["exec-time"], label="slurm", color="orange")
    ax1.plot(x1, results["batch"]["exec-time"], label="batch", color="blue")
    ax1.plot(x1, results["slurm"]["queue-time"], color="orange", linestyle="dashed")
    ax1.plot(x1, results["batch"]["queue-time"], color="blue", linestyle="dashed")
    ax1.legend()

    out_file = join(plots_dir, "motivation.{}".format(PLOTS_FORMAT))
    plt.savefig(out_file, format=PLOTS_FORMAT, bbox_inches="tight")
