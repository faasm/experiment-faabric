from glob import glob
from invoke import task
from os import makedirs
from os.path import join

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tasks.util.env import PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

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
                {"TimeInQueue": list}
            )
            for num_tasks in groupped_results["NumTasks"]:
                result_dict["tiq"][workload][num_tasks] = groupped_results.loc[
                    groupped_results["NumTasks"] == num_tasks, "TimeInQueue"
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
    makedirs(PLOTS_DIR, exist_ok=True)

    results = _read_results()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4))
    # First plot the CDF of the time spent in queue
    """
    for workload in results["tiq"]:
        for num_tasks in results["tiq"][workload]:
            data = results["tiq"][workload][num_tasks]
            ax1.hist(
                data,
                len(data),
                density=1,
                histtype="step",
                cumulative=True,
                label="{}: {} tasks".format(workload, num_tasks),
            )
    # Plot aesthetics
    ax1.set_xlim(left=0)
    ax1.set_ylim(bottom=0, top=1)
    ax1.legend(loc="upper left")
    ax1.set_xlabel("Time in queue [s]")
    ax1.set_ylabel("CDF")
    """
    # Alternatively, plot the mean and stdev of the time spent in queue
    """
    for workload in results["tiq"]:
        means = []
        stds = []
        for num_tasks in results["tiq"][workload]:
            means.append(np.mean(results["tiq"][workload][num_tasks]))
            stds.append(np.std(results["tiq"][workload][num_tasks]))
        ax1.errorbar(
            [nt for nt in results["tiq"][workload]],
            means,
            yerr=stds,
            fmt=".-",
            label="{}".format(workload),
            ecolor="gray",
            elinewidth=0.8,
        )
    # Plot aesthetics
    ax1.set_xlim(left=0)
    ax1.set_ylim(bottom=0, top=400)
    ax1.legend(loc="upper left")
    ax1.set_xlabel("Number of tasks")
    ax1.set_ylabel("Average time in queue [s]")
    """
    # First, plot the progress of execution per step
    num_steps = 100
    # Second, plot the makespan time
    for workload in results["makespan"]:
        data = results["makespan"][workload].items()
        ax2.plot(
            [i[0] for i in data], [i[1] for i in data], ".-", label=workload
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


#     n, bins, patches = ax.hist(x, n_bins, normed=1, histtype='step',
#                                cumulative=True, label='Empirical')
