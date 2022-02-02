from glob import glob
from invoke import task
from math import sqrt
from os import makedirs
from os.path import join, exists

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tasks.util.env import PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

RESULTS_DIR = join(PROJ_ROOT, "results", "kernels")
PLOTS_DIR = join(PLOTS_ROOT, "kernels")
NATIVE_CSV = join(RESULTS_DIR, "kernels_native.csv")
WASM_CSV = join(RESULTS_DIR, "kernels_wasm.csv")
OUT_FILE = join(PLOTS_DIR, "slowdown.{}".format(PLOTS_FORMAT))
XLABELS = {
    "p2p": "p2p\nMPI_{Send,Recv}",
    "transpose": "transpose\nMPI_{Isend,Irecv}",
    "reduce": "reduce\nMPI_Reduce",
    "sparse": "sparse\nMPI_Allgather",
}


def _read_results(exp):
    result_dict = {}

    for csv in glob(join(RESULTS_DIR, "kernels_{}_*.csv".format(exp))):
        # Blacklist two experiments we don't plot
        if ("stencil" in csv) or ("nstream" in csv):
            continue

        results = pd.read_csv(csv)

        # First filter only the timing stats, and then group by kernel
        results = results.loc[results["StatName"] == "Avg time (s)"]
        results = results.groupby("Kernel", as_index=False)

        # Second, group by world size
        for name, group in results:
            result_dict[name] = [
                group.groupby("WorldSize", as_index=False).mean(),
                group.groupby("WorldSize", as_index=False).sem(),
            ]

    return result_dict


def _check_results(native_results, wasm_results):
    """
    Check that both native and faasm experiments have:
    (1) Run with the same kernels
    (2) Run with the same number of processes
    """
    # If the two experiments recorded results for different kernels, error out
    if native_results.keys() != wasm_results.keys():
        print(
            "Kernels mismatch!\n - Native: {}\n - Faasm: {}".format(
                native_results.keys(), wasm_results.keys()
            )
        )
        return False

    # If the experiments run with different number of processes, error out
    for key in native_results.keys():
        if (
            native_results[key][0]["WorldSize"].count()
            != wasm_results[key][0]["WorldSize"].count()
        ):
            print("Number of processes in kernel {} mismatch!".format(key))
            print(
                " - Native: {}\n - Faasm: {}".format(
                    native_results[key][0], wasm_results[key][0]
                )
            )
            return False

    return True


def propagate_error(wasm_results, native_results, num_proc):
    """
    Propagate standard error when computing the slowdown (ratio) between two
    variables that already carry a standard error
    """
    wasm_times = [
        wasm_results[kern][0]["ActualTime"].tolist()[num_proc]
        for kern in wasm_results.keys()
    ]
    wasm_errs = [
        wasm_results[kern][1]["ActualTime"].tolist()[num_proc]
        for kern in wasm_results.keys()
    ]
    native_times = [
        native_results[kern][0]["ActualTime"].tolist()[num_proc]
        for kern in wasm_results.keys()
    ]
    native_errs = [
        native_results[kern][1]["ActualTime"].tolist()[num_proc]
        for kern in wasm_results.keys()
    ]

    yerr = []
    for wt, nt, werr, nerr in zip(
        wasm_times, native_times, wasm_errs, native_errs
    ):
        err = float(wt / nt) * sqrt(pow(werr / wt, 2) + pow(nerr / nt, 2))
        yerr.append(err)

    return yerr


@task
def plot(ctx):
    """
    Plot slowdown for MPI kernels
    """
    makedirs(PLOTS_DIR, exist_ok=True)

    # Load results and sanity check
    native_results = _read_results("native")
    wasm_results = _read_results("wasm")
    if not _check_results(native_results, wasm_results):
        return

    # Define the independent variables
    # Note that we must fit all the columns for each kernel, e.g. if n is odd:
    # ... [x - w - w /2, x - w/2] [x - w/2, x + w/2] [x + w/2, x + w + w/2] ...
    kernels = wasm_results.keys()
    num_procs = len(
        wasm_results[next(iter(wasm_results))][0]["WorldSize"].tolist()
    )
    xs = np.arange(len(kernels))
    xmin = xs[0] - 0.5
    xmax = xs[-1] + 0.5
    if (num_procs % 2) == 0:
        col_width = 0.5 / (0.5 + num_procs / 2)
        x_base = [x - (num_procs / 2 * col_width + col_width / 2) for x in xs]
    else:
        col_width = 0.5 / (1 + num_procs / 2)
        x_base = [x - (num_procs / 2 * col_width) for x in xs]

    # Define the dependent variables
    fig, ax = plt.subplots()
    y = []
    # We group the results by kernel, but plot them world size by world size,
    # in order to get the right x offset
    for num_proc in range(num_procs):
        wasm_times = [
            wasm_results[kern][0]["ActualTime"].tolist()[num_proc]
            for kern in wasm_results.keys()
        ]
        native_times = [
            native_results[kern][0]["ActualTime"].tolist()[num_proc]
            for kern in wasm_results.keys()
        ]
        # Each bar must be set at the midpoint of the right offset
        x = [x_b + num_proc * col_width + col_width / 2 for x_b in x_base]
        # We plot the slowdown
        y = [float(wt / nt) for wt, nt in zip(wasm_times, native_times)]
        ax.bar(
            x,
            y,
            width=col_width,
            yerr=propagate_error(wasm_results, native_results, num_proc),
        )

    # Prepare legend
    ax.legend(
        [
            "{} parallel functions".format(2 ** (num + 1))
            for num in range(num_procs)
        ],
        ncol=2,
    )

    # Aesthetics
    plt.hlines(1, xmin, xmax, linestyle="dashed", colors="red")
    plt.xlim(xmin, xmax)
    plt.ylim(0, 1.5)
    ax.set_xticks(xs)
    ax.set_xticklabels([XLABELS[key] for key in wasm_results.keys()])
    ax.set_ylabel("Slowdown [Faabric / OpenMPI]")
    plt.gca().set_aspect("equal")
    # ax.set_title("Kernels time to completion slowdown Faasm vs Native")
    fig.tight_layout()
    plt.savefig(OUT_FILE, format=PLOTS_FORMAT, bbox_inches="tight")
