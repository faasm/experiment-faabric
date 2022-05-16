from glob import glob
from invoke import task
from os import makedirs
from os.path import join

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tasks.util.env import MPL_STYLE_FILE, PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

RESULTS_DIR = join(PROJ_ROOT, "results", "makespan")
PLOTS_DIR = join(PLOTS_ROOT, "makespan")
OUT_FILE_TIQ = join(PLOTS_DIR, "time_in_queue.{}".format(PLOTS_FORMAT))


def _read_results():
    result_dict = {}

    for csv in glob(join(RESULTS_DIR, "makespan_*.csv")):
        workload = csv.split("_")[1]
        if "queue" in csv:
            result_type = "tiq"
        else:
            result_type = "makespan"
        if result_type not in result_dict:
            # result_dict[result_type] =
            #   {"native": {}, "wasm": {}, "batch": {}}
            result_dict[result_type] = {"wasm": {}, "batch": {}}

        # Read results
        results = pd.read_csv(csv)

        if result_type == "tiq":
            groupped_results = results.groupby("NumTasks", as_index=False).agg(
                {"TimeSinceStart": list}
            )
            for num_tasks in groupped_results["NumTasks"]:
                result_dict["tiq"][workload][num_tasks] = groupped_results.loc[
                    groupped_results["NumTasks"] == num_tasks, "TimeSinceStart"
                ].item()
        else:
            for num_tasks in results["NumTasks"]:
                result_dict["makespan"][workload][num_tasks] = results.loc[
                    results["NumTasks"] == num_tasks, "Makespan"
                ].item()

    print(result_dict["makespan"])

    return result_dict


@task(default=True)
def plot(ctx):
    """
    Plot makespan figures: CDF for time in queue and makespan plot
    """
    # Use our matplotlib style file
    plt.style.use(MPL_STYLE_FILE)

    makedirs(PLOTS_DIR, exist_ok=True)

    results = _read_results()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4))
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
        ax1.plot(xs, ys, label=workload)
    # Plot aesthetics
    ax1.set_xlim(left=0)
    ax1.set_ylim(bottom=0, top=100)
    ax1.legend(loc="upper left")
    ax1.set_xlabel("Time [s]")
    ax1.set_ylabel(
        "Workload completion (# tasks = {}) [%]".format(max_num_tasks)
    )
    # Second, plot the makespan time
    for workload in results["makespan"]:
        data = results["makespan"][workload]
        xs = [k for k in results["makespan"][workload].keys()]
        xs.sort()
        ax2.plot(
            xs, [data[x] for x in xs], label=workload
        )
    # Plot aesthetics
    ax2.set_xlim(left=0)
    ax2.set_ylim(bottom=0)
    ax2.legend(loc="upper left")
    ax2.set_xlabel("Number of tasks")
    ax2.set_ylabel("Makespan [s]")
    # Save multiplot to file
    fig.tight_layout()
    plt.savefig(OUT_FILE_TIQ, format=PLOTS_FORMAT, bbox_inches="tight")
