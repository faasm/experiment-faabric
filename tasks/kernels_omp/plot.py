from glob import glob
from invoke import task
from matplotlib.pyplot import subplots
from os import makedirs
from os.path import join
from pandas import read_csv
from tasks.util.env import OPENMP_KERNELS, PLOTS_ROOT, PROJ_ROOT


RESULTS_DIR = join(PROJ_ROOT, "results", "kernels-omp")
PLOTS_DIR = join(PLOTS_ROOT, "kernels-omp")


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

        for nt in groupped_results.mean()["NumThreads"].to_list():
            index = groupped_results.mean()["NumThreads"].to_list().index(nt)
            result_dict[baseline][workload][nt] = {
                "mean": groupped_results.mean()["ExecTimeSecs"].to_list()[
                    index
                ],
                "sem": groupped_results.sem()["ExecTimeSecs"].to_list()[index],
            }

    return result_dict


@task(default=True)
def plot(ctx):
    """
    Plot the slowdown of OpenMP's ParRes kernels
    """
    out_file_name = "openmp_kernels_slowdown.pdf"
    result_dict = _read_results()
    makedirs(PLOTS_DIR, exist_ok=True)
    fig, ax = subplots(figsize=(6, 2))

    num_kernels = len(OPENMP_KERNELS)
    width = float(1 / (num_kernels + 1))
    nprocs = list(range(1, 9))

    for ind_kernel, kernel in enumerate(OPENMP_KERNELS):
        ys = []
        xs = []
        x_kern_offset = -(num_kernels / 2) * width + ind_kernel * width
        if num_kernels % 2 == 0:
            x_kern_offset += width / 2

        for ind_np, np in enumerate(nprocs):
            xs.append(ind_np + x_kern_offset)
            y = (
                result_dict["granny"][kernel][np]["mean"]
                / result_dict["native"][kernel][np]["mean"]
            )
            ys.append(
                result_dict["granny"][kernel][np]["mean"]
                / result_dict["native"][kernel][np]["mean"]
            )
            ax.text(
                x=ind_np + x_kern_offset - 0.08,
                y=y + 0.1,
                s="{} s".format(result_dict["granny"][kernel][np]["mean"]),
                rotation=90,
                fontsize=6,
            )

        ax.bar(
            xs,
            ys,
            width,
            label=kernel,
            edgecolor="black",
        )

    # Labels
    xs = list(range(len(nprocs)))
    ax.set_xticks(xs, labels=nprocs)

    # Horizontal line at slowdown of 1
    xlim_left = -0.5
    xlim_right = len(nprocs) + 0.5
    fig.hlines(1, xlim_left, xlim_right, linestyle="dashed", colors="red")

    ymax = 5
    ax.set_ylim(bottom=0, top=ymax)
    ax.set_xlabel("Number of OpenMP threads")
    ax.set_ylabel("Slowdown \n [Granny / OpenMPI]")
    ax.legend(loc="upper right", ncol=4)

    fig.tight_layout()
    fig.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )

    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))
