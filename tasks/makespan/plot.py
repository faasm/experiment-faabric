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
COLORS = {
    "granny": (1, 0.4, 0.4),
    "native-1": (0.29, 0.63, 0.45),
    "native-2": (0.2, 0.6, 1.0),
    "native-4": (0.3, 0.3, 0.3),
    "native-8": (0.7, 0.6, 0.2),
}
LABELS = {
    "granny": "granny",
    "native-1": "1-ctr-per-vm",
    "native-2": "2-ctr-per-vm",
    "native-4": "4-ctr-per-vm",
    "native-8": "8-ctr-per-vm",
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
def plot(ctx, backend="k8s", num_vms=32, num_tasks=100, num_cores_per_vm=8):
    """
    Plot the number of idle cores over time for a specific trace and backend
    """
    mpi_trace = get_trace_from_parameters("mpi", num_tasks, num_cores_per_vm)
    omp_trace = get_trace_from_parameters("omp", num_tasks, num_cores_per_vm)
    num_vms = int(num_vms)
    out_file_name = "idle-cores_{}_{}_{}.pdf".format(
        backend, num_vms, mpi_trace[10:-4]
    )
    makedirs(PLOTS_DIR, exist_ok=True)
    plt.style.use(MPL_STYLE_FILE)

    fig, (ax_row1, ax_row2) = plt.subplots(nrows=2, ncols=3, figsize=(12, 8))

    # Plot one row of plots for MPI, and one for OpenMP
    _plot_row(ax_row1, "mpi", backend, num_vms, mpi_trace)
    _plot_row(ax_row2, "omp", backend, num_vms, omp_trace)

    # Finally, save the figure
    # TODO: will this work?
    fig.suptitle(
        "{} VMs - 100 Jobs - {} cores per VM (backend = {})".format(
            num_vms, get_num_cores_from_trace(mpi_trace), backend
        )
    )
    fig.tight_layout()
    plt.savefig(
        join(PLOTS_DIR, out_file_name), format="pdf", bbox_inches="tight"
    )

    print("Plot saved to: {}".format(join(PLOTS_DIR, out_file_name)))


def _plot_row(axes_row, workload_in, backend, num_vms, trace):
    """
    Plot one of the rows for each workload: `mpi` or `omp`
    """
    ax1 = axes_row[0]
    ax2 = axes_row[1]
    ax3 = axes_row[2]

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
        bar.set_label(LABELS[key])
        bar.set_color(COLORS[key])
    # ax1.legend()
    ax1.set_xticks(xs)
    ax1.set_xticklabels([LABELS[_l] for _l in labels], rotation=25, ha="right")
    ax1.set_ylim(bottom=0)
    ax1.set_ylabel("Makespan [s]")

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
        ax2.hist(
            xs,
            nbins,
            label=LABELS[workload],
            color=COLORS[workload],
            histtype="step",
            density=True,
            cumulative=True,
        )
    ax2.legend(loc="lower right")
    ax2.set_xlim(left=0, right=100)
    ax2.set_ylim(bottom=0, top=1)
    ax2.set_xlabel("Percentage of idle cores [%]")
    ax2.set_ylabel("CDF [%]")
    ax2.set_title("{}".format(workload_in))

    # Third plot: CDF of execution time and normalised (?) service time
    for workload in result_dict_et:
        xs = result_dict_et[workload]["exec-time"]
        ax3.hist(
            xs,
            nbins,
            label=LABELS[workload],
            color=COLORS[workload],
            histtype="step",
            density=True,
            cumulative=True,
        )
    ax3.legend(loc="upper left")
    ax3.set_xlim(left=0)
    ax3.set_ylim(bottom=0, top=1)
    ax3.set_xlabel("Execution Time [s]")
    ax3.set_ylabel("CDF [%]")
