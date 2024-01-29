from invoke import task
from math import sqrt
from matplotlib.pyplot import subplots
from os import makedirs
from os.path import join, exists
from pandas import read_csv
from tasks.util.env import PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

LAMMPS_WORKLOAD = "compute-xl"
RESULTS_DIR = join(PROJ_ROOT, "results", "lammps")
PLOTS_DIR = join(PLOTS_ROOT, "lammps")


def _read_results(csv):
    csv = join(RESULTS_DIR, csv)

    if not exists(csv):
        raise RuntimeError("CSV not found: {}".format(csv))

    results = read_csv(csv)

    grouped = results.groupby("WorldSize", as_index=False)
    times = grouped.mean()
    # Note that we use the standard error for correct error propagation
    errs = grouped.sem()

    return grouped, times, errs


@task(default=True)
def plot(ctx, plot_elapsed_times=True):
    """
    Plot the LAMMPS results
    """
    fig, ax = subplots(figsize=(6, 3))
    makedirs(PLOTS_DIR, exist_ok=True)
    plot_file = join(
        PLOTS_DIR, "runtime_{}.{}".format(LAMMPS_WORKLOAD, PLOTS_FORMAT)
    )

    # Process data
    native_csv = join(
        RESULTS_DIR, "lammps_native_{}.csv".format(LAMMPS_WORKLOAD)
    )
    wasm_csv = join(
        RESULTS_DIR, "lammps_granny_{}.csv".format(LAMMPS_WORKLOAD)
    )

    native_grouped, native_times, native_errs = _read_results(native_csv)
    wasm_grouped, wasm_times, wasm_errs = _read_results(wasm_csv)

    # Divide by first result to obtain speedup
    native_single = native_times["Time"][0]
    wasm_single = wasm_times["Time"][0]
    native_speedup = [native_single / time for time in native_times["Time"]]
    wasm_speedup = [wasm_single / time for time in wasm_times["Time"]]

    # Error propagation (for dummies)
    # https://www.dummies.com/education/science/biology/simple-error-propagation-formulas-for-simple-expressions/
    native_speedup_errs = []
    native_err_single = native_errs["Time"][0]
    for native_sup, native_e, native_t in zip(
        native_speedup, native_errs["Time"], native_times["Time"]
    ):
        native_speedup_errs.append(
            native_sup
            * sqrt(
                pow(native_err_single / native_single, 2)
                + pow(native_e / native_t, 2)
            )
        )
    wasm_speedup_errs = []
    wasm_err_single = wasm_errs["Time"][0]
    for wasm_sup, wasm_e, wasm_t in zip(
        wasm_speedup, wasm_errs["Time"], wasm_times["Time"]
    ):
        wasm_speedup_errs.append(
            wasm_sup
            * sqrt(
                pow(wasm_err_single / wasm_single, 2) + pow(wasm_e / wasm_t, 2)
            )
        )

    # Plot speed up data with error bars
    ax.errorbar(
        wasm_times["WorldSize"],
        wasm_speedup,
        yerr=wasm_speedup_errs,
        label="Granny",
        ecolor="gray",
        elinewidth=0.8,
        capsize=1.0,
    )
    ax.errorbar(
        native_times["WorldSize"],
        native_speedup,
        yerr=native_speedup_errs,
        label="OpenMPI",
        ecolor="gray",
        elinewidth=0.8,
        capsize=1.0,
    )

    # Plot elapsed time in a separate y axis
    if plot_elapsed_times:
        ax_et = ax.twinx()
        ax_et.errorbar(
            wasm_times["WorldSize"],
            wasm_times["Time"],
            yerr=wasm_errs["Time"],
            ecolor="gray",
            elinewidth=0.8,
            capsize=1.0,
            alpha=0.3,
        )
        ax_et.errorbar(
            native_times["WorldSize"],
            native_times["Time"],
            yerr=native_errs["Time"],
            ecolor="gray",
            elinewidth=0.8,
            capsize=1.0,
            alpha=0.3,
        )
        ax_et.set_ylabel("Elapsed time [s]")
        ax_et.set_ylim(bottom=0)

        ax.set_ylim(bottom=0)
        ax.set_xlim(left=0)
        ax.set_xticks([2 * i for i in range(9)])
        ax.set_xlabel("# of processes")
        ax.set_ylabel("Speed Up (vs 1 MPI Proc performance)")

    ax.legend()
    fig.savefig(plot_file, format=PLOTS_FORMAT, bbox_inches="tight")
