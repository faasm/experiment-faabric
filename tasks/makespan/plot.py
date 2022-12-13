from glob import glob
from invoke import task
from numpy import arange
from os import makedirs
from os.path import join
from tasks.makespan.util import (
    get_num_cores_from_trace,
    get_trace_ending,
    get_trace_from_parameters,
)
from tasks.util.env import MPL_STYLE_FILE, PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT
from tasks.util.plot import PLOT_COLORS, PLOT_LABELS, PLOT_PATTERNS

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

RESULTS_DIR = join(PROJ_ROOT, "results", "makespan")
PLOTS_DIR = join(PLOTS_ROOT, "makespan")
OUT_FILE_TIQ = join(PLOTS_DIR, "time_in_queue.{}".format(PLOTS_FORMAT))
WORKLOAD_TO_LABEL = {
    "wasm": "Granny",
    "batch": "Batch (1 usr)",
    "batch2": "Batch (2 usr)",
}


def _read_results(plot, workload, backend, num_vms, trace):
    result_dict = {}

    if plot == "idle-cores":
        glob_str = "makespan_idle-cores_*_{}_{}_{}".format(
            backend, num_vms, get_trace_ending(trace)
        )
        for csv in glob(join(RESULTS_DIR, glob_str)):
            workload = csv.split("_")[2]
            results = pd.read_csv(csv)
            result_dict[workload] = results["NumIdleCores"].to_list()
    elif plot == "exec-time":
        trace_ending = trace[6:]
        glob_str = "makespan_exec-task-info_*_{}_{}_{}".format(
            backend, num_vms, trace_ending
        )
        for csv in glob(join(RESULTS_DIR, glob_str)):
            workload = csv.split("_")[2]
            results = pd.read_csv(csv)
            result_dict[workload] = {}
            result_dict[workload]["makespan"] = (
                results.max()["EndTimeStamp"] - results.min()["StartTimeStamp"]
            )
            result_dict[workload]["exec-time"] = results[
                "TimeExecuting"
            ].to_list()
            result_dict[workload]["service-time"] = (
                results["TimeExecuting"] + results["TimeInQueue"]
            ).to_list()

    return result_dict


@task(default=True)
def saturation(
    ctx, backend="k8s", num_vms=32, num_tasks=100, num_cores_per_vm=8
):
    """
    Plot the makespan, number of idle cores over time, and execution time
    when the cluster is saturated
    """
    mpi_trace = get_trace_from_parameters("mpi", num_tasks, num_cores_per_vm)
    omp_trace = get_trace_from_parameters("omp", num_tasks, num_cores_per_vm)
    num_vms = int(num_vms)
    makedirs(PLOTS_DIR, exist_ok=True)
    plt.style.use(MPL_STYLE_FILE)

    # Plot one row of plots for MPI, and one for OpenMP, and one for mix
    _plot_row("mpi", backend, num_vms, mpi_trace)
    _plot_row("omp", backend, num_vms, omp_trace)


def _plot_row(workload_in, backend, num_vms, trace):
    """
    Plot one of the rows for each workload: `mpi` or `omp`
    """
    out_file_name = "idle-cores_{}_{}_{}_{}.pdf".format(
        workload_in, backend, num_vms, trace[10:-4]
    )
    fig, (ax1, ax2, ax3) = plt.subplots(nrows=1, ncols=3, figsize=(12, 2))

    # First plot: breakdown of makespans
    result_dict_et = _read_results(
        "exec-time", workload_in, backend, num_vms, trace
    )
    num_workloads = len(result_dict_et)
    width = 0.5
    xs = arange(num_workloads)
    labels = list(result_dict_et.keys())
    labels.sort()
    ys = [result_dict_et[la]["makespan"] for la in labels]
    bars = ax1.bar(xs, ys, width)
    for bar, key in zip(bars, labels):
        bar.set_label(PLOT_LABELS[key])
        bar.set_color(PLOT_COLORS[key])
        bar.set_hatch(PLOT_PATTERNS[labels.index(key)])
        bar.set_edgecolor("black")
    ax1.set_ylim(bottom=0)
    ax1.set_ylabel("Makespan [s]")
    ax1.set_xticks(xs)
    ax1.set_xticklabels(
        [PLOT_LABELS[_l] for _l in labels], rotation=25, ha="right"
    )

    # Second plot: CDF of idle cores
    result_dict_ic = _read_results(
        "idle-cores", workload_in, backend, num_vms, trace
    )
    total_num_cores = num_vms * get_num_cores_from_trace(trace)
    nbins = 100
    for workload in result_dict_ic:
        xs = [
            int(ic / total_num_cores * 100) for ic in result_dict_ic[workload]
        ]
        bars = ax2.hist(
            xs,
            nbins,
            color=PLOT_COLORS[workload],
            histtype="step",
            density=True,
            cumulative=True,
        )
    ax2.set_xlim(left=0, right=100)
    ax2.set_ylim(bottom=0, top=1)
    ax2.set_ylabel("CDF [%]")
    ax2.set_xlabel("Percentage of idle vCPUs [%]")

    # Third plot: CDF of execution time and normalised (?) service time
    for workload in result_dict_et:
        xs = result_dict_et[workload]["exec-time"]
        ax3.hist(
            xs,
            nbins,
            color=PLOT_COLORS[workload],
            histtype="step",
            density=True,
            cumulative=True,
        )
    ax3.set_xlim(left=0)
    ax3.set_ylim(bottom=0, top=1)
    ax3.set_ylabel("CDF [%]")
    ax3.set_xlabel("Execution Time [s]")

    # Finally, save the figure
    fig.tight_layout()
    plt.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )
    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))


@task()
def mods(ctx, backend="k8s", num_vms=32, num_tasks=100, num_cores_per_vm=8):
    """
    # Second figure: MPI with migration, and OpenMP with consolidation
    out_file_name = "mods_{}_{}_{}.pdf".format(
        backend, num_vms, mpi_trace[10:-4]
    )
    fig, (ax_row1, ax_row2) = plt.subplots(
        nrows=2, ncols=3, figsize=(12, 8)
    )
    _plot_row(ax_row1, "mpi-migrate", backend, num_vms, mpi_migrate_trace)
    # TODO: make this OpenMP consolidate instead
    _plot_row(ax_row2, "mpi-migrate", backend, num_vms, mpi_migrate_trace)
    fig.tight_layout()
    plt.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )
    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))
    """
    pass


@task(default=False)
def scaling(
    ctx, backend="k8s", num_vms=None, num_tasks=None, num_cores_per_vm=8
):
    if not num_vms:
        num_vms = [16, 32, 64, 128]
    else:
        num_vms = [int(num_vms)]
    if not num_tasks:
        num_tasks = [50, 100, 200, 400]
    else:
        num_tasks = [int(num_tasks)]

    if len(num_tasks) != len(num_vms):
        raise RuntimeError(
            "Lengths differ! {} != {}".format(len(num_tasks), len(num_vms))
        )

    traces = []
    for tasks in num_tasks:
        traces.append(
            get_trace_from_parameters("mpi", tasks, num_cores_per_vm)
        )

    makedirs(PLOTS_DIR, exist_ok=True)
    plt.style.use(MPL_STYLE_FILE)

    result_dict_et = {}
    for num_vm, trace in zip(num_vms, traces):
        result_dict_et[num_vm] = _read_results(
            "exec-time", "mpi", backend, num_vm, trace
        )

    makespans = {}
    exec_times = {}
    labels = list(PLOT_LABELS.keys())
    labels.sort()
    for label in labels:
        for num_vm in num_vms:
            if label not in makespans:
                makespans[label] = []
                exec_times[label] = []
            makespans[label].append(result_dict_et[num_vm][label]["makespan"])
            exec_times[label].append(
                result_dict_et[num_vm][label]["exec-time"]
            )

    # First plot: bar plot of makespans
    out_file_name = "scaling_{}_makespan.pdf".format(backend)
    fig, ax = plt.subplots(figsize=(4, 3))
    width = 0.15
    xs = arange(len(num_vms))
    for ind, label in enumerate(labels):
        ax.bar(
            xs - width * 2 + width * ind,
            makespans[label],
            width,
            label=PLOT_LABELS[label],
            color=PLOT_COLORS[label],
            hatch=PLOT_PATTERNS[ind],
            edgecolor="black",
        )
    ax.set_ylabel("Makespan [s]", fontsize=12)
    xlabels = [
        "{} VMs\n{} jobs".format(num_vm, ntasks)
        for num_vm, ntasks in zip(num_vms, num_tasks)
    ]
    ax.set_xticks(xs)
    ax.set_xticklabels(xlabels, rotation=25, ha="center", fontsize=12)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    plt.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )
    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))

    # Second plot: box plot of execution times
    out_file_name = "scaling_{}_exec_time.pdf".format(backend)
    fig, ax = plt.subplots(figsize=(4, 3))
    legend_handles = []
    for ind, label in enumerate(labels):
        bplot = ax.boxplot(
            exec_times[label],
            positions=[x - width * 2 + width * ind for x in xs],
            widths=width,
            patch_artist=True,
            flierprops=dict(
                marker=".",
                markerfacecolor=PLOT_COLORS[label],
                markersize=1,
                linestyle="none",
                markeredgecolor=PLOT_COLORS[label],
            ),
            boxprops=dict(linewidth=0),
            medianprops=dict(color="black", linewidth=1),
            whiskerprops=dict(linewidth=1),
            showfliers=False,
            vert=True,
        )
        for box in bplot["boxes"]:
            box.set_facecolor(PLOT_COLORS[label])
            box.set_hatch(PLOT_PATTERNS[labels.index(label)])
        legend_handles.append(
            mpatches.Patch(
                facecolor=PLOT_COLORS[label],
                hatch=PLOT_PATTERNS[ind],
                edgecolor="black",
                lw=1,
                label=label,
            )
        )
    ax.legend(
        handles=legend_handles, loc="upper left", ncol=2, prop={"size": 12}
    )
    ax.set_ylim(bottom=0, top=300)
    ax.set_xticks(xs)
    ax.set_xticklabels(xlabels, rotation=25, ha="center", fontsize=12)
    ax.set_ylabel("Execution time [s]", fontsize=12)
    fig.tight_layout()
    plt.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )
    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))
