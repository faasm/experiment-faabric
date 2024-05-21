from invoke import task
from matplotlib.patches import Patch
from matplotlib.pyplot import subplots
from os import makedirs
from os.path import join
from tasks.util.env import PLOTS_ROOT
from tasks.util.locality import plot_locality_results, read_locality_results
from tasks.util.plot import (
    get_color_for_baseline,
    get_label_for_baseline,
    save_plot,
)
from tasks.util.spot import plot_spot_results, read_spot_results

MOTIVATION_PLOTS_DIR = join(PLOTS_ROOT, "motivation")


@task(default=True)
def locality(ctx):
    """
    Plot the motivation figure illustrating the trade-off between locality and
    utilisation
    """
    num_vms = 32
    num_tasks = 200
    num_cpus_per_vm = 8

    results = {}
    results[num_vms] = read_locality_results(
        num_vms, num_tasks, num_cpus_per_vm
    )
    makedirs(MOTIVATION_PLOTS_DIR, exist_ok=True)

    # ----------
    # Plot 1: timeseries of the percentage of idle vCPUs
    # ----------

    fig, ax1 = subplots(figsize=(6, 2))
    plot_locality_results("ts_vcpus", results, ax1, num_vms=num_vms, num_tasks=num_tasks)

    # Manually craft the legend
    baselines = ["slurm", "batch", "granny-migrate"]
    legend_entries = [
        Patch(
            color=get_color_for_baseline("mpi-migrate", baseline),
            label=get_label_for_baseline("mpi-migrate", baseline),
        )
        for baseline in baselines
    ]
    fig.legend(
        handles=legend_entries,
        loc="upper center",
        ncols=len(baselines),
        bbox_to_anchor=(0.52, 1.07),
    )

    save_plot(fig, MOTIVATION_PLOTS_DIR, "motivation_vcpus")

    # ----------
    # Plot 2: timeseries of the number of cross-VM links
    # ----------

    fig, ax2 = subplots(figsize=(6, 2))
    plot_locality_results("ts_xvm_links", results, ax2, num_vms=num_vms, num_tasks=num_tasks)
    save_plot(fig, MOTIVATION_PLOTS_DIR, "motivation_xvm_links")


@task
def spot(ctx):
    """
    Subset of the makespan.spot plot to include in the motivation section
    """
    num_vms = [32]
    num_tasks = [100]
    num_cpus_per_vm = 8

    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_spot_results(n_vms, n_tasks, num_cpus_per_vm)

    # ----------
    # Plot 1: makespan slowdown (spot / no spot)
    # ----------

    fig, ax1 = subplots(figsize=(2, 2))
    plot_spot_results(
        "makespan",
        results,
        ax1,
        num_vms=num_vms,
        num_tasks=num_tasks,
        tight=True,
    )

    # Manually craft the legend
    """
    baselines = ["slurm", "batch", "granny"]
    legend_entries = [
        Patch(
            color=get_color_for_baseline("mpi-spot", baseline),
            label=get_label_for_baseline("mpi-spot", baseline)
        ) for baseline in baselines
    ]
    fig.legend(
        handles=legend_entries,
        loc="upper center",
        ncols=len(baselines),
        bbox_to_anchor=(0.52, 1.07)
    )
    """

    save_plot(fig, MOTIVATION_PLOTS_DIR, "motivation_spot_makespan")

    # ----------
    # Plot 2: stacked cost bar plot (spot) + real cost (no spot)
    # ----------

    fig, ax2 = subplots(figsize=(2, 2))
    plot_spot_results(
        "cost",
        results,
        ax2,
        num_vms=num_vms,
        num_tasks=num_tasks,
        tight=True,
    )

    save_plot(fig, MOTIVATION_PLOTS_DIR, "motivation_spot_cost")
