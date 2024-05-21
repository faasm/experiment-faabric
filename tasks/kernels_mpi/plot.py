from glob import glob
from invoke import task
from matplotlib.pyplot import subplots
from os import makedirs
from os.path import join
from pandas import read_csv
from tasks.util.env import SYSTEM_NAME
from tasks.util.kernels import (
    MPI_KERNELS_EXPERIMENT_NPROCS,
    MPI_KERNELS_FAASM_FUNCS,
    MPI_KERNELS_PLOTS_DIR,
    MPI_KERNELS_RESULTS_DIR,
)
from tasks.util.plot import UBENCH_PLOT_COLORS, SINGLE_COL_FIGSIZE, save_plot


def _read_kernels_results():
    result_dict = {}

    for csv in glob(join(MPI_KERNELS_RESULTS_DIR, "kernels_*.csv")):
        results = read_csv(csv)

        baseline = csv.split("_")[1]
        kernel = csv.split("_")[-1].split(".")[0]

        groupped_results = results.groupby("WorldSize", as_index=False)
        if baseline not in result_dict:
            result_dict[baseline] = {}
        if kernel not in result_dict[baseline]:
            result_dict[baseline][kernel] = {}

        for np in groupped_results.mean()["WorldSize"].to_list():
            index = groupped_results.mean()["WorldSize"].to_list().index(np)
            result_dict[baseline][kernel][np] = {
                "mean": groupped_results.mean()["ActualTime"].to_list()[index],
                "sem": groupped_results.sem()["ActualTime"].to_list()[index],
            }

    return result_dict


@task(default=True)
def kernels(ctx):
    """
    Plot the slowdown of MPI's ParRes kernels
    """
    result_dict = _read_kernels_results()
    makedirs(MPI_KERNELS_PLOTS_DIR, exist_ok=True)
    fig, ax = subplots(figsize=SINGLE_COL_FIGSIZE)

    num_kernels = len(MPI_KERNELS_FAASM_FUNCS)
    width = float(1 / (num_kernels + 1))

    ymax = 2
    for ind_kernel, kernel in enumerate(MPI_KERNELS_FAASM_FUNCS):
        ys = []
        xs = []
        x_kern_offset = -(num_kernels / 2) * width + ind_kernel * width
        if num_kernels % 2 == 0:
            x_kern_offset += width / 2
        for ind_np, np in enumerate(MPI_KERNELS_EXPERIMENT_NPROCS):
            xs.append(ind_np + x_kern_offset)
            in_granny = np in result_dict["granny"][kernel]
            in_native = np in result_dict["native"][kernel]
            if (in_granny) and (in_native):
                y = (
                    result_dict["granny"][kernel][np]["mean"]
                    / result_dict["native"][kernel][np]["mean"]
                )
                if y > ymax:
                    ax.text(
                        x=ind_np + x_kern_offset - 0.05,
                        y=ymax - 0.3,
                        s="{}x".format(round(y, 1)),
                        rotation=90,
                        fontsize=6,
                    )

                    ys.append(ymax)
                else:
                    ys.append(y)
            else:
                print(
                    "Skipping {} with {} MPI procs "
                    "(in granny: {} - in native: {})".format(
                        kernel, np, in_granny, in_native
                    )
                )
                ys.append(0)

        ax.bar(
            xs,
            ys,
            width,
            color=UBENCH_PLOT_COLORS[ind_kernel],
            label=kernel,
            edgecolor="black",
        )

    # Labels
    xs = list(range(len(MPI_KERNELS_EXPERIMENT_NPROCS)))
    ax.set_xticks(xs, labels=MPI_KERNELS_EXPERIMENT_NPROCS)

    # Horizontal line at slowdown of 1
    xlim_left = -0.5
    xlim_right = len(MPI_KERNELS_EXPERIMENT_NPROCS) - 0.5
    ax.hlines(1, xlim_left, xlim_right, linestyle="dashed", colors="red")

    # Vertical lines to separate MPI processes
    ylim_bottom = 0
    ylim_top = ymax
    """
    ax.vlines(
        [i + 0.5 for i in range(len(MPI_KERNELS_EXPERIMENT_NPROCS) - 1)],
        ylim_bottom,
        ylim_top,
        linestyle="dashed",
        colors="gray",
    )
    """

    ax.set_xlim(left=xlim_left, right=xlim_right)
    ax.set_ylim(bottom=ylim_bottom, top=ylim_top)
    ax.set_xlabel("Number of MPI processes")
    ax.set_ylabel("Slowdown \n [{} / OpenMPI]".format(SYSTEM_NAME))
    ax.legend(loc="upper right", ncol=4)

    save_plot(fig, MPI_KERNELS_PLOTS_DIR, "mpi_kernels_slowdown")
