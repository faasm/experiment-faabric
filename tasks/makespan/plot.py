from glob import glob
from invoke import task
from os import makedirs
from os.path import join
from tasks.makespan.util import get_num_cores_from_trace
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


def _read_results(plot, backend, num_vms, trace):
    result_dict = {}

    if plot == "idle-cores":
        trace_ending = trace[6:]
        glob_str = "makespan_idle-cores_*_{}_{}_{}".format(backend, num_vms, trace_ending)
        print(glob_str)
        for csv in glob(join(RESULTS_DIR, glob_str)):
            workload = csv.split("_")[2]
            results = pd.read_csv(csv)
            result_dict[workload] = [
                results["TimeStampSecs"].to_list(),
                results["NumIdleCores"].to_list(),
            ]

    return result_dict


@task(default=True)
def plot(ctx):
    """
    Plot makespan figures: percentage of progression and makespan time
    """
    # Use our matplotlib style file
    plt.style.use(MPL_STYLE_FILE)

    makedirs(PLOTS_DIR, exist_ok=True)

    results = _read_results()

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


@task()
def idle_cores(ctx, backend="compose", num_vms=4, trace=None):
    """
    Plot the number of idle cores over time for a specific trace and backend
    """
    result_dict = _read_results("idle-cores", backend, num_vms, trace)
    out_file_name = "idle-cores_{}_{}_{}.pdf".format(backend, num_vms, trace[6:-4])
    makedirs(PLOTS_DIR, exist_ok=True)
    plt.style.use(MPL_STYLE_FILE)
    total_num_cores = num_vms * get_num_cores_from_trace(trace)

    fig, ax = plt.subplots(figsize=(6, 3))
    for workload in result_dict:
        total_time = max(result_dict[workload][0])
        xs = result_dict[workload][0]
        ys = [int(i)/total_num_cores for i in result_dict[workload][1] * 100]
        ax.plot(xs, ys, label=workload)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0, top=100)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Percentage of idle cores [%]")
    ax.set_title("Number of idle cores over time (backend = {})".format(backend))

    fig.tight_layout()

    plt.savefig(join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight")
