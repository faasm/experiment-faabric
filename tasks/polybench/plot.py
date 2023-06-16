from glob import glob
from invoke import task
from pandas import read_csv as pd_read_csv
from os import makedirs
from os.path import join
from tasks.polybench.util import POLYBENCH_FUNCS
from tasks.util.env import MPL_STYLE_FILE, PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

import matplotlib.pyplot as plt


def _read_results(baseline):
    results_dir = join(PROJ_ROOT, "results", "polybench")
    result_dict = {}

    for csv in glob(join(results_dir, "polybench_{}_*.csv".format(baseline))):
        poly_bench = "poly_{}".format(csv.split("_")[-1].split(".")[0])
        if poly_bench not in POLYBENCH_FUNCS:
            raise RuntimeError(
                "Unrecognised poly bench: {}".format(poly_bench)
            )

        results = pd_read_csv(csv)
        result_dict[poly_bench] = {}

        result_dict[poly_bench] = {
            "mean": results.mean()["Time"],
            "sem": results.sem()["Time"],
        }

    return result_dict


def _check_results(native_results, granny_results):
    if len(native_results) != len(granny_results):
        raise RuntimeError(
            "Different number of kernels for native ({}) and granny ({})".format(
                len(native_results), len(granny_results)
            )
        )

    if len(native_results) != len(POLYBENCH_FUNCS):
        raise RuntimeError(
            "Different number of results ({}) than expected ({})".format(
                len(native_results), len(POLYBENCH_FUNCS)
            )
        )

    return True


@task(default=True)
def plot(ctx):
    """
    Plot PolyBench/C micro-benchmark (slowdown vs native)
    """
    # Use our matplotlib style file
    plt.style.use(MPL_STYLE_FILE)

    plots_dir = join(PLOTS_ROOT, "polybench")
    makedirs(plots_dir, exist_ok=True)

    # Load results and sanity check
    native_results = _read_results("native")
    granny_results = _read_results("granny")

    if not _check_results(native_results, granny_results):
        return

    # Plot the benchmarks in alphabetical order
    poly_benchmarks = list(granny_results.keys())
    poly_benchmarks.sort()

    # Define the dependent variables
    fig, ax = plt.subplots(figsize=(6, 3))
    x = range(len(poly_benchmarks))
    y = [
        granny_results[poly_bench]["mean"] / native_results[poly_bench]["mean"]
        for poly_bench in poly_benchmarks
    ]
    ax.bar(
        x,
        y,
        # width=col_width,
        # TODO: propagate error
        # yerr=propagate_error(wasm_results, native_results, num_proc),
        # hatch=PATTERNS[num],
        edgecolor="black",
    )

    # Aesthetics
    xmin = -0.5
    xmax = len(poly_benchmarks) - 0.5
    plt.hlines(1, xmin, xmax, linestyle="dashed", colors="red")
    plt.xlim(xmin, xmax)
    ax.set_xticks(range(len(poly_benchmarks)))
    ax.set_xticklabels(
        [pb.split("_")[1] for pb in poly_benchmarks],
        rotation=45,
        fontsize=10,
        ha="right",
    )
    ax.set_ylabel("Slowdown [WASM / Native]")
    fig.tight_layout()

    out_file = join(plots_dir, "slowdown.{}".format(PLOTS_FORMAT))
    plt.savefig(out_file, format=PLOTS_FORMAT, bbox_inches="tight")
