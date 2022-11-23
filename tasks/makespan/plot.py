from glob import glob
from invoke import task
from numpy import arange
from os import makedirs
from os.path import join
from tasks.makespan.util import (
    get_num_cores_from_trace,
)
from tasks.util.env import MPL_STYLE_FILE, PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

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
COLORS = {
    "granny": (1, 0.4, 0.4),
    "native-1": (0.29, 0.63, 0.45),
    "native-2": (0.2, 0.6, 1.0),
    "native-4": (0.3, 0.3, 0.3),
    "native-8": (0.7, 0.6, 0.2),
}


def _read_results(plot, backend, num_vms, trace):
    result_dict = {}

    if plot == "idle-cores":
        trace_ending = trace[6:]
        glob_str = "makespan_idle-cores_*_{}_{}_{}".format(
            backend, num_vms, trace_ending
        )
        for csv in glob(join(RESULTS_DIR, glob_str)):
            workload = csv.split("_")[2]
            results = pd.read_csv(csv)
            result_dict[workload] = results["NumIdleCores"].to_list()
    elif plot == "exec-time":
        trace_ending = trace[6:]
        glob_str = "makespan_exec-task-info_*_{}_{}_{}".format(
            backend, num_vms, trace_ending
        )
        for csv in glob(join(RESULTS_DIR, glob_str)):
            workload = csv.split("_")[2]
            results = pd.read_csv(csv)
            result_dict[workload] = {}
            result_dict[workload]["makespan"] = (
                results.max()["EndTimeStamp"] - results.min()["StartTimeStamp"]
            )
            result_dict[workload]["exec-time"] = results[
                "TimeExecuting"
            ].to_list()
            result_dict[workload]["service-time"] = (
                results["TimeExecuting"] + results["TimeInQueue"]
            ).to_list()

    return result_dict


@task(default=True)
def plot(ctx, backend="compose", num_vms=4, trace=None):
    """
    Plot makespan figures: percentage of progression and makespan time
    """
    # Use our matplotlib style file
    plt.style.use(MPL_STYLE_FILE)
    makedirs(PLOTS_DIR, exist_ok=True)
    result_dict = _read_results("exec-time", backend, num_vms, trace)
    print(result_dict)
    return

    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6, 3))
    # First, plot the progress of execution per step
    # Pick the highest task for a better progress line
    max_num_tasks = max(results["tiq"]["wasm"].keys())
    for workload in results["tiq"]:
        time_points = results["tiq"][workload][max_num_tasks]
        time_points.sort()
        xs = time_points
        ys = [
            (num + 1) / len(time_points) * 100
            for num in range(len(time_points))
        ]
        ax1.plot(xs, ys, label=WORKLOAD_TO_LABEL[workload])
    # Plot aesthetics
    ax1.set_xlim(left=0)
    ax1.set_ylim(bottom=0, top=100)
    ax1.legend(loc="lower right")
    ax1.set_xlabel("Time [s]")
    ax1.set_ylabel(
        "Workload completion (# jobs = {}) [%]".format(max_num_tasks)
    )
    # Second, plot the makespan time
    for workload in results["makespan"]:
        data = results["makespan"][workload]
        xs = [k for k in results["makespan"][workload].keys()]
        xs.sort()
        print("{}: {}".format(workload, xs))
        print("{}: {}".format(workload, [data[x] for x in xs]))
        ax2.plot(xs, [data[x] for x in xs], label=WORKLOAD_TO_LABEL[workload])
    # Plot aesthetics
    ax2.set_xlim(left=0)
    ax2.set_ylim(bottom=0)
    # ax2.legend(loc="lower right")
    ax2.set_xlabel("Number of jobs")
    ax2.set_ylabel("Makespan [s]")
    # Save multiplot to file
    fig.tight_layout()
    plt.savefig(OUT_FILE_TIQ, format=PLOTS_FORMAT, bbox_inches="tight")
    """


@task()
def idle_cores(ctx, backend, num_vms, trace=None):
    """
    Plot the number of idle cores over time for a specific trace and backend
    """
    num_vms = int(num_vms)
    out_file_name = "idle-cores_{}_{}_{}.pdf".format(
        backend, num_vms, trace[6:-4]
    )
    makedirs(PLOTS_DIR, exist_ok=True)
    plt.style.use(MPL_STYLE_FILE)

    fig, (ax1, ax2, ax3) = plt.subplots(nrows=1, ncols=3, figsize=(12, 4))

    # First plot: breakdown of makespans
    result_dict_et = _read_results("exec-time", backend, num_vms, trace)
    num_workloads = len(result_dict_et)
    width = 0.5
    xs = arange(num_workloads)
    ys = [result_dict_et[wload]["makespan"] for wload in result_dict_et]
    bars = ax1.bar(xs, ys, width)  # , label=workload, color=COLORS[workload]
    for bar, key in zip(bars, result_dict_et.keys()):
        bar.set_label(key)
        bar.set_color(COLORS[key])
    # ax1.legend()
    ax1.set_xticks(xs)
    ax1.set_xticklabels(list(result_dict_et.keys()))
    ax1.set_ylim(bottom=0)
    ax1.set_ylabel("Makespan [s]")

    # Second plot: CDF of idle cores
    result_dict_ic = _read_results("idle-cores", backend, num_vms, trace)
    total_num_cores = num_vms * get_num_cores_from_trace(trace)
    nbins = 100
    for workload in result_dict_ic:
        xs = [
            int(ic / total_num_cores * 100) for ic in result_dict_ic[workload]
        ]
        ax2.hist(
            xs,
            nbins,
            label=workload,
            color=COLORS[workload],
            histtype="step",
            density=True,
            cumulative=True,
        )
    ax2.legend(loc="upper left")
    ax2.set_xlim(left=0, right=100)
    ax2.set_ylim(bottom=0, top=1)
    ax2.set_xlabel("Percentage of idle cores [%]")
    ax2.set_ylabel("CDF [%]")
    ax2.set_title(
        "{} VMs - 100 Jobs - {} cores per VM (backend = {})".format(
            num_vms, get_num_cores_from_trace(trace), backend
        )
    )

    # Third plot: CDF of execution time and normalised (?) service time
    for workload in result_dict_et:
        xs = result_dict_et[workload]["exec-time"]
        ax3.hist(
            xs,
            nbins,
            label=workload,
            color=COLORS[workload],
            histtype="step",
            density=True,
            cumulative=True,
        )
    ax3.legend(loc="upper left")
    ax3.set_xlim(left=0)
    ax3.set_ylim(bottom=0, top=1)
    ax3.set_xlabel("Execution Time [s]")
    ax3.set_ylabel("CDF [%]")

    fig.tight_layout()

    plt.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )
