from glob import glob
from invoke import task
from numpy import arange
from os import makedirs
from os.path import join
from pandas import read_csv
from tasks.util.env import PLOTS_ROOT, PROJ_ROOT
from tasks.util.plot import PLOT_COLORS, PLOT_PATTERNS

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
        if baseline not in result_dict:
            result_dict[baseline] = {}
        if workload not in result_dict[baseline]:
            result_dict[baseline][workload] = {}
        result_dict[baseline][workload] = {
            "num-threads": groupped_results.mean()["NumThreads"].to_list(),
            "mean": groupped_results.mean()["ExecTimeSecs"].to_list(),
            "sem": groupped_results.sem()["ExecTimeSecs"].to_list(),
        }

    return result_dict


@task(default=True)
def plot(ctx):
    out_file_name = "openmp_slowdown.pdf"
    result_dict = _read_results()
    makedirs(PLOTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 2))
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16]
    xticks = arange(1, len(xs) + 1)
    num_ctrs_per_vm = 8
    width = 0.25
    ymax = 10.5
    for ind, workload in enumerate(result_dict["granny"]):
        ys = []
        for x_ind, x in enumerate(xs):
            try:
                idx_granny = result_dict["granny"][workload][
                    "num-threads"
                ].index(x)
                if x > num_ctrs_per_vm:
                    idx_native = result_dict["native-1"][workload][
                        "num-threads"
                    ].index(num_ctrs_per_vm)
                else:
                    idx_native = result_dict["native-1"][workload][
                        "num-threads"
                    ].index(x)
                yval = float(
                        result_dict["granny"][workload]["mean"][idx_granny]
                        / result_dict["native-1"][workload]["mean"][idx_native]
                    )
                ys.append(yval)
                if yval > ymax:
                    plt.text(xticks[x_ind] - 0.4, ymax/2, "{}x".format(int(yval)), fontdict={"rotation": 90})
            except ValueError:
                ys.append(0)
        print(ys)
        barlist = ax.bar(
            [x - width * 0.5 + width * ind for x in xticks],
            ys,
            width,
            label=workload,
            color=list(PLOT_COLORS.values())[ind],
            hatch=PLOT_PATTERNS[ind],
            edgecolor="black",
        )
        for ind, bar in enumerate(barlist):
            if ind >= num_ctrs_per_vm:
                bar.set_alpha(0.5)
    ax.set_xlim(left=0)
    ax.set_xlabel("Number of OpenMP threads")
    print(xticks)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xs)
    ax.set_ylim(bottom=0, top=ymax)
    plt.vlines(8.5, 0, ymax, linestyle="dashed", color="gray")
    plt.text(8.5 - 1, ymax + 0.5, "VM capacity")
    plt.hlines(1, 0, 17, linestyle="dashed", colors="red")
    ax.legend(loc="upper left", ncol=1)
    ax.set_ylabel("Slowdown \n [Granny / OpenMP]")

    fig.tight_layout()
    plt.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )

    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))
