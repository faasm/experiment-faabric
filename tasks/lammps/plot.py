from os import makedirs, sysconf, sysconf_names
from os.path import join, exists, expanduser

from math import sqrt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.figure import figaspect
import numpy as np
import pandas as pd
from invoke import task
from hoststats.results import HostStatsResults

from tasks.util.env import PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

RESULTS_DIR = join(PROJ_ROOT, "results", "lammps")
PLOTS_DIR = join(PLOTS_ROOT, "lammps")

BENCHMARKS = ["compute", "network"]
PLOT_COORDS = [0, 1]

# Each tuple in the list contains the resource name in the hoststats result
# object, the unit to display in the Y axis, and whether the measure is an
# accumulated value or not.
ALL_RESOURCES = [
    ["CPU_PCT", "%", False],
    [
        "CPU_TIME_IOWAIT",
        "1/{} sec".format(sysconf(sysconf_names["SC_CLK_TCK"])),
        True,
    ],
    [
        "CPU_TIME_IDLE",
        "1/{} sec".format(sysconf(sysconf_names["SC_CLK_TCK"])),
        True,
    ],
    ["MEMORY_USED_PCT", "%", False],
    ["DISK_READ_MB", "MB", True],
    ["NET_SENT_MB", "MB", True],
]


def _read_results(csv):
    csv = join(RESULTS_DIR, csv)

    if not exists(csv):
        raise RuntimeError("CSV not found: {}".format(csv))

    results = pd.read_csv(csv)

    grouped = results.groupby("WorldSize", as_index=False)
    times = grouped.mean()
    # Note that we use the standard error for correct error propagation
    errs = grouped.sem()

    return grouped, times, errs


@task(default=True)
def plot(ctx, gui=False, plot_elapsed_times=True):
    """
    Plot the LAMMPS results
    """
    fig, ax = plt.subplots(nrows=1, ncols=2, sharex=True, figsize=(6, 3))
    makedirs(PLOTS_DIR, exist_ok=True)
    plot_file = join(PLOTS_DIR, "runtime.{}".format(PLOTS_FORMAT))

    #     fig.suptitle(
    #         "LAMMPS speed-up Faasm vs OpenMPI\n(overlayed with elapsed time)"
    #     )

    for bench, coords in zip(BENCHMARKS, PLOT_COORDS):
        # Process data
        native_csv = join(RESULTS_DIR, "lammps_native_{}.csv".format(bench))
        wasm_csv = join(RESULTS_DIR, "lammps_wasm_{}.csv".format(bench))

        native_grouped, native_times, native_errs = _read_results(native_csv)
        wasm_grouped, wasm_times, wasm_errs = _read_results(wasm_csv)

        # Divide by first result to obtain speedup
        native_single = native_times["Actual"][0]
        wasm_single = wasm_times["Actual"][0]
        native_speedup = [
            native_single / time for time in native_times["Actual"]
        ]
        wasm_speedup = [wasm_single / time for time in wasm_times["Actual"]]

        # Error propagation (for dummies)
        # https://www.dummies.com/education/science/biology/simple-error-propagation-formulas-for-simple-expressions/
        native_speedup_errs = []
        native_err_single = native_errs["Actual"][0]
        for native_sup, native_e, native_t in zip(
            native_speedup, native_errs["Actual"], native_times["Actual"]
        ):
            native_speedup_errs.append(
                native_sup
                * sqrt(
                    pow(native_err_single / native_single, 2)
                    + pow(native_e / native_t, 2)
                )
            )
        wasm_speedup_errs = []
        wasm_err_single = wasm_errs["Actual"][0]
        for wasm_sup, wasm_e, wasm_t in zip(
            wasm_speedup, wasm_errs["Actual"], wasm_times["Actual"]
        ):
            wasm_speedup_errs.append(
                wasm_sup
                * sqrt(
                    pow(wasm_err_single / wasm_single, 2)
                    + pow(wasm_e / wasm_t, 2)
                )
            )

        # Plot speed up data with error bars
        ax[coords].errorbar(
            wasm_times["WorldSize"],
            wasm_speedup,
            yerr=wasm_speedup_errs,
            fmt=".-",
            label="Faabric",
            ecolor="gray",
            elinewidth=0.8,
            capsize=1.0,
        )
        ax[coords].errorbar(
            native_times["WorldSize"],
            native_speedup,
            yerr=native_speedup_errs,
            fmt=".-",
            label="OpenMPI",
            ecolor="gray",
            elinewidth=0.8,
            capsize=1.0,
        )

        if plot_elapsed_times:
            # Plot elapsed time in a separate y axis
            ax_et = ax[coords].twinx()
            ax_et.errorbar(
                wasm_times["WorldSize"],
                wasm_times["Actual"],
                yerr=wasm_errs["Actual"],
                fmt=".--",
                label="Faabric",
                ecolor="gray",
                elinewidth=0.8,
                capsize=1.0,
                alpha=0.3,
            )
            ax_et.errorbar(
                native_times["WorldSize"],
                native_times["Actual"],
                yerr=native_errs["Actual"],
                fmt=".--",
                label="OpenMPI",
                ecolor="gray",
                elinewidth=0.8,
                capsize=1.0,
                alpha=0.3,
            )
            if coords == 1:
                ax_et.set_ylabel("Elapsed time [s]")
            ax_et.set_ylim(bottom=0)

        ax[coords].title.set_text("{}-bound benchmark".format(bench))
        ax[coords].set_ylim(bottom=0)
        ax[coords].set_xlim(left=0)
        ax[coords].set_xticks([2 * i for i in range(9)])
        ax[coords].set_xlabel("# of parallel functions")
        if coords == 0:
            ax[coords].set_ylabel("Speed Up (vs 1 MPI Proc performance)")

    # Print legend
    handles, labels = ax[1].get_legend_handles_labels()
    fig.legend(handles, labels, bbox_to_anchor=(0.22, 0.79), loc="center")

    fig.tight_layout()

    # Set aspect ratio

    # Manually add common axis labels
    # fig.text(0.015, 0.5, "", ha="center", va="center", rotation="vertical")

    if gui:
        fig.show()
    else:
        fig.savefig(plot_file, format=PLOTS_FORMAT, bbox_inches="tight")


@task
def plot_resources(ctx, world_size, run=0, gui=False):
    native_file = join(
        RESULTS_DIR,
        "hoststats_native_compute_{}_{}.csv".format(world_size, run),
    )

    wasm_file = join(
        RESULTS_DIR, "hoststats_wasm_compute_{}_{}.csv".format(world_size, run)
    )

    native_stats = HostStatsResults(native_file)
    wasm_stats = HostStatsResults(wasm_file)

    makedirs(PLOTS_ROOT, exist_ok=True)
    plot_file = join(PLOTS_DIR, "resources.png")

    fig = plt.figure()
    fig.suptitle("World size {}, run {}".format(world_size, run))

    ax = plt.subplot(221)
    plot_hoststats_resource(ax, native_stats, wasm_stats, "CPU_PCT", "%")

    ax = plt.subplot(222)
    plot_hoststats_resource(ax, native_stats, wasm_stats, "MEMORY_USED", "MB")

    ax = plt.subplot(223)
    plot_hoststats_resource(ax, native_stats, wasm_stats, "DISK_READ_MB", "MB")

    ax = plt.subplot(224)
    plot_hoststats_resource(ax, native_stats, wasm_stats, "NET_SENT_MB", "MB")

    handles, labels = ax.get_legend_handles_labels()
    plt.legend(handles, labels)

    plt.tight_layout()

    if gui:
        plt.show()
    else:
        plt.savefig(plot_file, format=PLOTS_FORMAT)


@task
def resources_cmp_runs(ctx, bench, run_one, run_two, run=0, gui=False):
    """
    Compare the resource usage of two runs of the same benchmark identified by
    their world size.
    """
    fig = plt.figure(figsize=(16, 8))
    outer = gridspec.GridSpec(2, 1)

    makedirs(PLOTS_ROOT, exist_ok=True)
    plot_file = join(
        PLOTS_DIR, "resources_{}_{}vs{}.png".format(bench, run_one, run_two)
    )

    for num, world_size in enumerate([int(run_one), int(run_two)]):
        # Set the outer frame for a single run
        ax = plt.Subplot(fig, outer[num], frameon=False, xticks=[], yticks=[])
        ax.set_title(
            "MPI World Size: {}".format(world_size), fontweight="bold", y=1.1
        )
        fig.add_subplot(ax)

        # Set the inner grid for all resources in a single run
        inner = gridspec.GridSpecFromSubplotSpec(
            1,
            len(ALL_RESOURCES),
            subplot_spec=outer[num],
            wspace=0.4,
            hspace=0,
        )

        plot_single_run(plt, fig, inner, bench, world_size)

    plt.tight_layout()
    plt.suptitle("")

    if gui:
        plt.show()
    else:
        plt.savefig(plot_file, format=PLOTS_FORMAT)


def plot_single_run(plt, fig, grid, bench, world_size, run=0):
    native_file = join(
        RESULTS_DIR,
        "hoststats_native_{}_{}_{}.csv".format(bench, world_size, run),
    )
    wasm_file = join(
        RESULTS_DIR,
        "hoststats_wasm_{}_{}_{}.csv".format(bench, world_size, run),
    )

    try:
        native_stats = HostStatsResults(native_file)
    except RuntimeError:
        print("native stats file not found")
        return
    try:
        wasm_stats = HostStatsResults(wasm_file)
    except RuntimeError:
        print("wasm stats file not found")
        return

    for index, tup in enumerate(ALL_RESOURCES):
        resource = tup[0]
        unit = tup[1]
        is_acc = tup[2]

        ax = plt.Subplot(fig, grid[index])
        plot_hoststats_resource(
            ax, native_stats, wasm_stats, resource, unit, is_acc, per_host=True
        )

        # Plot legend only on the first run
        if index == 0:
            handles, labels = ax.get_legend_handles_labels()
            fig.legend(handles, labels)

        fig.add_subplot(ax)


def plot_hoststats_resource(
    ax,
    native_stats: HostStatsResults,
    wasm_stats: HostStatsResults,
    stat,
    y_label,
    is_acc,
    per_host=False,
):
    ax.set_title("{}".format(stat), fontsize="small")

    if per_host:
        wasm_series_per_host = wasm_stats.get_stat_per_host(stat)
        for host in wasm_series_per_host:
            if is_acc:
                ax.plot(
                    wasm_series_per_host[host]["Timestamp"].dt.total_seconds(),
                    wasm_series_per_host[host][stat].diff(),
                    label=host.split("-")[-1],
                )
                continue

            ax.plot(
                wasm_series_per_host[host]["Timestamp"].dt.total_seconds(),
                wasm_series_per_host[host][stat],
                label=host.split("-")[-1],
            )

        native_series_per_host = native_stats.get_stat_per_host(stat)
        for host in native_series_per_host:
            if is_acc:
                ax.plot(
                    native_series_per_host[host][
                        "Timestamp"
                    ].dt.total_seconds(),
                    native_series_per_host[host][stat].diff(),
                    label=host.split("-")[-1],
                    ls="--",
                )
                continue

            ax.plot(
                native_series_per_host[host]["Timestamp"].dt.total_seconds(),
                native_series_per_host[host][stat],
                label=host.split("-")[-1],
                ls="--",
            )
    else:
        if is_acc:
            wasm_series = wasm_stats.get_median_stat(stat).diff()
        else:
            wasm_series = wasm_stats.get_median_stat(stat)
        wasm_series.index = wasm_series.index.total_seconds()
        wasm_series.plot(ax=ax, label="Faabric")

        if is_acc:
            native_series = native_stats.get_median_stat(stat).diff()
        else:
            native_series = native_stats.get_median_stat(stat)
        native_series.index = native_series.index.total_seconds()
        native_series.plot(ax=ax, label="OpenMPI")

    ax.set_ylim(bottom=0)
    ax.set_xlim(left=0)

    ax.set_ylabel(y_label, fontsize="small")
    ax.set_xlabel("Time (s)", fontsize="small")
