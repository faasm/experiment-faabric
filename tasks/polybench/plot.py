from glob import glob
from invoke import task
from numpy import arange
from os import makedirs
from os.path import join
from tasks.util.env import PLOTS_ROOT, PROJ_ROOT
from tasks.util.plot import PLOT_COLORS, PLOT_PATTERNS

import matplotlib.pyplot as plt
import pandas as pd


ALL_WORKLOADS = ["lammps", "all-to-all"]


def _read_results():
    results_dir = join(PROJ_ROOT, "results", "migration")
    result_dict = {}

    for csv in glob(join(results_dir, "migration_*.csv")):
        workload = csv.split("_")[-1].split(".")[0]
        if workload not in ["lammps", "all-to-all"]:
            continue

        results = pd.read_csv(csv)
        groupped_results = results.groupby("Check", as_index=False)

        if workload not in result_dict:
            result_dict[workload] = {}

        result_dict[workload] = {
            "checks": groupped_results.mean()["Check"].to_list(),
            "mean": groupped_results.mean()["Time"].to_list(),
            "sem": groupped_results.sem()["Time"].to_list(),
        }

    return result_dict


@task(default=True)
def plot(ctx):
    """
    Plot migration figure
    """
    migration_results = _read_results()

    # First plot: all-to-all kernel
    do_plot("all-to-all", migration_results)
    do_plot("lammps", migration_results)


def do_plot(workload, migration_results):
    plots_dir = join(PLOTS_ROOT, "migration")
    makedirs(plots_dir, exist_ok=True)
    out_file = join(plots_dir, "migration_speedup_{}.pdf".format(workload))
    fig, ax = plt.subplots(figsize=(3, 2))
    xs = [0, 2, 4, 6, 8]
    xticks = arange(1, 6)
    width = 0.5
    idx_ref = migration_results[workload]["checks"].index(10)
    ind = ALL_WORKLOADS.index(workload)
    ys = []
    for x in xs:
        idx_granny = migration_results[workload]["checks"].index(x)
        ys.append(
            float(
                migration_results[workload]["mean"][idx_ref]
                / migration_results[workload]["mean"][idx_granny]
            )
        )
    ax.bar(
        xticks,
        ys,
        width,
        label=workload,
        color=list(PLOT_COLORS.values())[ind],
        hatch=PLOT_PATTERNS[ind],
        edgecolor="black",
    )
    # Aesthetics
    ax.set_ylabel("Speed-up \n [No mig. / mig.]")
    ax.set_xlabel("% of execution when to migrate")
    ax.set_xticks(xticks)
    ax.set_xticklabels(["1 VM", "20", "40", "60", "80"])
    xlim_left = 0.5
    xlim_right = 5.5
    ax.set_xlim(left=xlim_left, right=xlim_right)
    ax.set_ylim(bottom=0)
    plt.hlines(1, xlim_left, xlim_right, linestyle="dashed", colors="red")
    fig.tight_layout()
    plt.savefig(out_file, format="pdf")  # , bbox_inches="tight")
    print("Plot saved to: {}".format(out_file))
