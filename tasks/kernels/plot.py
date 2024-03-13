from glob import glob
from invoke import task
from matplotlib.pyplot import subplots
from os import makedirs
from os.path import join
from pandas import read_csv
from tasks.util.env import PLOTS_ROOT, PROJ_ROOT
from tasks.util.kernels import KERNELS_EXPERIMENT_NPROCS, KERNELS_FAASM_FUNCS

PLOTS_DIR = join(PLOTS_ROOT, "kernels-mpi")


def _read_kernels_results():
    result_dict = {}
    results_dir = join(PROJ_ROOT, "results", "kernels-mpi")

    for csv in glob(join(results_dir, "kernels_*.csv")):
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
    out_file_name = "mpi_kernels_slowdown.pdf"
    result_dict = _read_kernels_results()
    makedirs(PLOTS_DIR, exist_ok=True)
    fig, ax = subplots()

    num_kernels = len(KERNELS_FAASM_FUNCS)
    width = float(1 / (num_kernels + 1))

    for ind_kernel, kernel in enumerate(KERNELS_FAASM_FUNCS):
        ys = []
        xs = []
        x_kern_offset = -(num_kernels / 2) * width + ind_kernel * width
        if num_kernels % 2 == 0:
            x_kern_offset += width / 2
        for ind_np, np in enumerate(KERNELS_EXPERIMENT_NPROCS):
            xs.append(ind_np + x_kern_offset)
            in_granny = np in result_dict["granny"][kernel]
            in_native = np in result_dict["native"][kernel]
            if (in_granny) and (in_native):
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
            label=kernel,
            edgecolor="black",
        )

    # Labels
    xs = list(range(len(KERNELS_EXPERIMENT_NPROCS)))
    ax.set_xticks(xs, labels=KERNELS_EXPERIMENT_NPROCS)

    # Horizontal line at slowdown of 1
    xlim_left = -0.5
    xlim_right = len(KERNELS_EXPERIMENT_NPROCS) + 0.5
    fig.hlines(1, xlim_left, xlim_right, linestyle="dashed", colors="red")

    # Vertical lines to separate MPI processes
    ylim_bottom = 0
    ylim_top = 5
    fig.vlines(
        [i + 0.5 for i in range(len(KERNELS_EXPERIMENT_NPROCS) - 1)],
        ylim_bottom,
        ylim_top,
        linestyle="dashed",
        colors="gray",
    )

    ax.set_xlim(left=xlim_left, right=xlim_right)
    ax.set_ylim(bottom=ylim_bottom, top=ylim_top)
    ax.set_xlabel("Number of MPI processes")
    ax.set_ylabel("Slowdown \n [Granny / OpenMPI]")
    ax.legend(loc="upper right", ncol=4)

    fig.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )

    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))
