from glob import glob
from matplotlib.patches import Patch
from numpy import linspace
from os.path import join
from pandas import read_csv
from scipy.interpolate import CubicSpline
from tasks.util.env import (
    PLOTS_ROOT,
    RESULTS_DIR,
)
from tasks.util.plot import PLOT_COLORS

MAKESPAN_RESULTS_DIR = join(RESULTS_DIR, "makespan")
MAKESPAN_PLOTS_DIR = join(PLOTS_ROOT, "makespan")


def read_spot_results(num_vms, num_tasks, num_cpus_per_vm):
    result_dict = {}

    glob_str = "makespan_makespan_*_{}_mpi-spot_{}_{}.csv".format(
        num_vms, num_tasks, num_cpus_per_vm
    )
    for csv in glob(join(MAKESPAN_RESULTS_DIR, glob_str)):
        baseline = csv.split("_")[2]
        results = read_csv(csv)
        result_dict[baseline] = {}

        # -----
        # Results to visualise makespan
        # -----

        makespan_s = results["MakespanSecs"].to_list()
        assert len(makespan_s) == 1, "Too many rows: expected 1, got {}!".format(len(makespan_s))
        makespan_s = makespan_s[0]
        result_dict[baseline]["makespan"] = makespan_s

        print(
            "Num VMs: {} - Num Tasks: {} - Baseline: {} - Makespan: {}s".format(
                num_vms, num_tasks, baseline, makespan_s
            )
        )

    return result_dict


def _do_plot_makespan(results, ax, **kwargs):
    assert "num_vms" in kwargs, "num_vms not in kwargs!"
    assert "num_tasks" in kwargs, "num_tasks not in kwargs!"
    num_vms = kwargs["num_vms"]
    num_tasks = kwargs["num_tasks"]

    if "tight" in kwargs:
        tight = kwargs["tight"]
    else:
        tight = False

    baselines = ["slurm", "batch", "granny"]

    xs = []
    ys = []
    colors = []
    xticks = []
    xticklabels = []

    for ind, n_vms in enumerate(num_vms):
        x_offset = ind * len(baselines) + (ind + 1)
        xs += [x + x_offset for x in range(len(baselines))]
        ys += [
            float(results[n_vms][baseline + "-ft"]["makespan"]) / float(results[n_vms][baseline]["makespan"])
            for baseline in baselines
        ]
        colors += [PLOT_COLORS[la] for la in baselines]

        # Add one tick and xlabel per VM size
        xticks.append(x_offset + len(baselines) / 2)
        xticklabels.append(
            "{} VMs\n({} Jobs)".format(n_vms, num_tasks[ind])
        )

        # Add spacing between vms
        if ind != len(num_vms) - 1:
            xs.append(x_offset + len(baselines))
            ys.append(0)
            colors.append("white")

    ax.bar(xs, ys, color=colors, edgecolor="black", width=1)
    ax.set_ylim(bottom=0)
    if tight:
        ax.set_ylabel("Slowdown [Spot / No Spot]", fontsize=6)
        ax.tick_params(axis='y', labelsize=6)
    else:
        ax.set_ylabel("Makespan Slowdown \n [Spot VMs / No Spot VMs]")

    ax.set_xticks(xticks, labels=xticklabels, fontsize=6)

    # Manually craft legend
    legend_entries = []
    for baseline in baselines:
        legend_entries.append(
            Patch(color=PLOT_COLORS[baseline], label=baseline)
        )

    if tight:
        ax.legend(handles=legend_entries, ncols=1, fontsize=6, loc="lower center")
    else:
        ax.legend(handles=legend_entries, ncols=1, fontsize=8)


def _do_plot_cost(results, ax, **kwargs):
    assert "num_vms" in kwargs, "num_vms not in kwargs!"
    assert "num_tasks" in kwargs, "num_tasks not in kwargs!"
    num_vms = kwargs["num_vms"]
    num_tasks = kwargs["num_tasks"]

    if "tight" in kwargs:
        tight = kwargs["tight"]
    else:
        tight = False

    baselines = ["slurm", "batch", "granny"]
    # Put discounts in decreasing order so that we can stack values on top of
    # each other in increasing order
    discounts_pcnt = [90, 60, 30]

    xs = []
    colors = []
    xticks = []
    xticklabels = []

    nospot_xs = []
    nospot_ys = []

    ys = {}
    for discount in discounts_pcnt:
        ys[discount] = []

    for ind, n_vms in enumerate(num_vms):
        x_offset = ind * len(baselines) + (ind + 1)
        xs += [x + x_offset for x in range(len(baselines))]
        nospot_xs += [x + x_offset for x in range(len(baselines))]

        for discount in discounts_pcnt:
            ys[discount] += [
                float(results[n_vms][baseline + "-ft"]["makespan"]) * (1 - discount / 100) / 3600
                for baseline in baselines
            ]
            if ind != len(num_vms) - 1:
                ys[discount].append(0)

        nospot_ys += [results[n_vms][baseline]["makespan"] / 3600 for baseline in baselines]
        colors += [PLOT_COLORS[la] for la in baselines]

        # Add one tick and xlabel per VM size
        xticks.append(x_offset + len(baselines) / 2)
        xticklabels.append(
            "{} VMs\n({} Jobs)".format(n_vms, num_tasks[ind])
        )

        # Add spacing between vms
        if ind != len(num_vms) - 1:
            xs.append(x_offset + len(baselines))
            colors.append("white")

    bottom_ys = []
    for ind, discount in enumerate(discounts_pcnt):
        if ind == 0:
            ax.bar(xs, ys[discount], color=colors, edgecolor="black", width=1)
        else:
            this_ys = [y - bottom_y for y, bottom_y in zip(ys[discount], bottom_ys)]
            ax.bar(
                xs,
                this_ys,
                bottom=bottom_ys,
                color=colors,
                edgecolor="black",
                alpha=float(discount / 100.0),
                width=1
            )

        # Add disccount annotation
        if tight:
            ax.text(
                xs[-2] * 0.92,
                ys[discount][-2] + 0.001,
                "{}% off".format(discount),
                fontsize=6,
            )
        else:
            ax.text(
                xs[-1] + 0.5,
                ys[discount][-1] + 0.0001,
                "{}% off".format(discount),
                fontsize=6,
                rotation=90,
            )

        bottom_ys = ys[discount]

    # Also plot the cost of running in regular (no-spot VMs)
    ax.plot(
        nospot_xs,
        nospot_ys,
        color="black",
        linestyle="-",
        marker=".",
        label="Cost without Spot VMs" if not tight else "Cost No Spot",
    )

    ax.set_ylim(bottom=0)
    if tight:
        ax.set_ylabel("Cost [Hours / $]", fontsize=6)
        ax.tick_params(axis='y', labelsize=6)
        ax.legend(fontsize=6)
    else:
        ax.set_ylabel("Normalized Cost [Hours / $]")
        ax.legend(fontsize=8)
    ax.set_xticks(xticks, labels=xticklabels, fontsize=6)


def plot_spot_results(plot_name, results, ax, **kwargs):
    if plot_name == "makespan":
        _do_plot_makespan(results, ax, **kwargs)
    elif plot_name == "cost":
        _do_plot_cost(results, ax, **kwargs)
    else:
        raise RuntimeError("Unrecognised plot name: {}".format(plot_name))
