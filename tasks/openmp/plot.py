from glob import glob
from invoke import task
from os import makedirs
from os.path import join
from pandas import read_csv
from tasks.util.env import PLOTS_ROOT, PROJ_ROOT
from tasks.util.plot import PLOT_COLORS, PLOT_LABELS

import matplotlib.pyplot as plt

RESULTS_DIR = join(PROJ_ROOT, "results", "openmp")
PLOTS_DIR = join(PLOTS_ROOT, "openmp")


def _read_results():
    result_dict = {}

    for csv in glob(join(RESULTS_DIR, "openmp_*.csv")):
        results = read_csv(csv)

        workload = csv.split("_")[1]
        baseline = csv.split("_")[-1].split(".")[0]

        groupped_results = results.groupby("NumThreads", as_index=False)
        if workload not in result_dict:
            result_dict[workload] = {}
        if baseline not in result_dict[workload]:
            result_dict[workload] = {}
        result_dict[workload][baseline] = [
            groupped_results.mean()["NumThreads"].to_list(),
            groupped_results.mean()["ExecTimeSecs"].to_list(),
            groupped_results.sem()["ExecTimeSecs"].to_list(),
        ]

    return result_dict


@task(default=True)
def plot(ctx):
    out_file_name = "openmp_dgemm.pdf"
    result_dict = _read_results()
    makedirs(PLOTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 2))
    for baseline in result_dict["dgemm"]:
        ax.errorbar(
            result_dict["dgemm"][baseline][0],
            result_dict["dgemm"][baseline][1],
            result_dict["dgemm"][baseline][2],
            marker="o",
            linestyle="-",
            label=PLOT_LABELS[baseline],
            color=PLOT_COLORS[baseline],
            ecolor="gray",
        )
    ax.set_xlim(left=0)
    ax.set_xlabel("Number of OpenMP threads")
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Execution time [s]")

    fig.tight_layout()
    plt.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )

    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))
