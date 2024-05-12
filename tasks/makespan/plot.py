from invoke import task
from matplotlib.patches import Patch
from matplotlib.pyplot import subplots, subplot_mosaic
from tasks.util.elastic import (
    plot_elastic_results,
    read_elastic_results,
)
from tasks.util.eviction import (
        read_eviction_results,
        plot_eviction_results,
)
# TODO: consider moving some of the migration to a different file (e.g.
# tasks.util.locality)
from tasks.util.makespan import (
    MAKESPAN_PLOTS_DIR,
    do_makespan_plot,
    read_makespan_results,
)
from tasks.util.plot import (
    get_color_for_baseline,
    get_label_for_baseline,
    save_plot,
)
from tasks.util.spot import (
    plot_spot_results,
    read_spot_results,
)


@task
def migration(ctx):
    """
    Macrobenchmark plot showing the benefits of migrating MPI applications to
    improve locality of execution
    """
    # num_vms = [16, 24, 32, 48, 64]
    # num_tasks = [50, 75, 100, 150, 200]
    num_vms = [16]
    exec_cdf_num_vms = 16
    num_tasks = [50]
    num_cpus_per_vm = 8

    # Read results from files
    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_makespan_results(n_vms, n_tasks, num_cpus_per_vm)

    fig, (ax1, ax2) = subplots(nrows=1, ncols=2)  # , figsize=(6, 3))
    fig.subplots_adjust(wspace=0.35)

    # ----------
    # Plot 1: CDF of Job-Completion-Time
    # ----------

    # do_plot("exec_vs_tiq", results, ax1, num_vms, num_tasks)
    do_makespan_plot("exec_cdf", results, ax1, exec_cdf_num_vms, num_tasks)

    # ----------
    # Plot 2: Job Churn
    # ----------

    # WARNING: the "makespan" plot is the only one that reads num_vms as
    # an array
    do_makespan_plot("makespan", results, ax2, num_vms, num_tasks)

    # ----------
    # Save figure
    # ----------

    save_plot(fig, MAKESPAN_PLOTS_DIR, "mpi_migration")


@task
def locality(ctx):
    """
    Macrobenchmark plot showing the benefits of migrating MPI applications to
    improve locality of execution. We show:
    - LHS: both number of cross-VM links and number of idle cpu cores per exec
    - RHS: timeseries of one of the points in the plot
    """
    num_vms = [8, 16, 24, 32]
    num_tasks = [50, 100, 150, 200]
    num_cpus_per_vm = 8

    # RHS: zoom in one of the bars
    timeseries_num_vms = 32
    timeseries_num_tasks = 200

    # WARN: this assumes that we never repeat num_vms with different numbers of
    # num_tasks (fair at this point)
    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_makespan_results(n_vms, n_tasks, num_cpus_per_vm)

    fig, (ax1, ax2, ax3, ax4) = subplots(nrows=1, ncols=4, figsize=(12, 3))

    # ----------
    # Plot 1: boxplot of idle vCPUs and num xVM links for various cluster sizes
    # ----------

    do_makespan_plot(
        "percentage_vcpus",
        results,
        ax1,
        num_vms,
        num_tasks
    )

    do_makespan_plot(
        "percentage_xvm",
        results,
        ax2,
        num_vms,
        num_tasks
    )

    # ----------
    # Plot 2: (two) timeseries of one of the cluster sizes
    # ----------

    do_makespan_plot(
        "ts_vcpus",
        results,
        ax3,
        timeseries_num_vms,
        timeseries_num_tasks
    )

    do_makespan_plot(
        "ts_xvm_links",
        results,
        ax4,
        timeseries_num_vms,
        timeseries_num_tasks
    )

    # Manually craft the legend
    baselines = ["slurm", "batch", "granny", "granny-migrate"]
    legend_entries = [
        Patch(
            color=get_color_for_baseline("mpi-migrate", baseline),
            label=get_label_for_baseline("mpi-migrate", baseline)
        ) for baseline in baselines
    ]
    fig.legend(
        handles=legend_entries,
        loc="upper center",
        ncols=len(baselines),
        bbox_to_anchor=(0.52, 1.07)
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_locality")


@task
def eviction(ctx):
    """
    Macrobenchmark plot showing the benefits of migrating MPI applications to
    evict idle VMs.
    - LHS: Bar plot of the VMseconds used per execution (makespan)
    - RHS: timeseries of the number of active jobs per user
    """
    # num_vms = [8, 16, 32]
    # num_tasks = [50, 100, 200]
    num_vms = [8, 16]
    num_tasks = [50, 100]
    num_users = [10, 10]
    num_cpus_per_vm = 8

    # RHS: zoom in one of the bars
    timeseries_num_vms = 8
    timeseries_num_users = 10

    results = {}
    for (n_vms, n_users, n_tasks) in zip(num_vms, num_users, num_tasks):
        results[n_vms] = read_eviction_results(n_vms, n_users, n_tasks, num_cpus_per_vm)

    fig, ax = subplot_mosaic([['left', 'right'],
                              ['left', 'right']])

    # ----------
    # Plot 1: bar plot of the CPUsecs per execution
    # ----------

    plot_eviction_results(
        "makespan",
        results,
        ax["left"],
        num_vms=num_vms,
        num_tasks=num_tasks,
        num_users=num_users,
    )

    # ----------
    # Plot 2: timeseries of one of the cluster sizes
    # ----------

    plot_eviction_results(
        "tasks_per_user",
        results,
        ax["right"],
        num_vms=timeseries_num_vms,
        num_users=timeseries_num_users,
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "eviction")


@task
def spot(ctx):
    """
    Macro-benchmark showing the benefits of using Granny to run on SPOT VMs.
    - LHS: makespan slowdown wrt not using SPOT VMs (makespan_spot / makespan_no_spot)
    - RHS: cost savings of using SPOT VMs (price_spot / price_no_spot). We
           use different savings percentages of using spot VMs from 90% (maximum
           reported by Azure) to 25% (90, 75, 50, 25)
    """
    num_vms = [8, 16, 24, 32]
    num_tasks = [25, 50, 75, 100]
    num_cpus_per_vm = 8

    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_spot_results(n_vms, n_tasks, num_cpus_per_vm)

    fig, (ax1, ax2) = subplots(nrows=1, ncols=2, figsize=(6, 3))

    # ----------
    # Plot 1: makespan slowdown (spot / no spot)
    # ----------

    plot_spot_results(
        "makespan",
        results,
        ax1,
        num_vms=num_vms,
        num_tasks=num_tasks,
    )

    # ----------
    # Plot 2: stacked cost bar plot (spot) + real cost (no spot)
    # ----------

    plot_spot_results(
        "cost",
        results,
        ax2,
        num_vms=num_vms,
        num_tasks=num_tasks,
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "spot")


@task
def elastic(ctx):
    """
    Macro-benchmark showing the benefits of using Granny to elastically scale
    up shared memory applications to use idle vCPU cores.
    We want to show:
    - Each job runs for shorter -> CDF of JCT
    - Overall we run for shorter -> Makespan
    - We have less idle vCPU cores -> same idle plot from locality
    - We should also have a timeseries of the idle vCPU plots

    Initial idea is to have four columns
    """
    # num_vms = [8, 16, 24, 32]
    # num_tasks = [25, 50, 75, 100]
    num_vms = [4, 8]
    num_tasks = [10, 25]
    num_cpus_per_vm = 8

    # RHS: zoom in one of the bars
    timeseries_num_vms = num_vms[-1]
    timeseries_num_tasks = num_tasks[-1]
    cdf_num_vms = timeseries_num_vms
    cdf_num_tasks = timeseries_num_tasks

    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_elastic_results(n_vms, n_tasks, num_cpus_per_vm)

    fig, (ax1, ax2, ax3, ax4) = subplots(nrows=1, ncols=4, figsize=(12, 3))

    # ----------
    # Plot 1: makespan
    # ----------

    plot_elastic_results(
        "makespan",
        results,
        ax1,
        num_vms=num_vms,
        num_tasks=num_tasks,
    )

    # ----------
    # Plot 2: percentage of idle vCPUs
    # ----------

    plot_elastic_results(
        "percentage_vcpus",
        results,
        ax2,
        num_vms=num_vms,
        num_tasks=num_tasks,
        num_cpus_per_vm=num_cpus_per_vm,
    )

    # ----------
    # Plot 3: CDF of the JCT (for one run)
    # ----------

    plot_elastic_results(
        "cdf_jct",
        results,
        ax3,
        cdf_num_vms=cdf_num_vms,
        cdf_num_tasks=cdf_num_tasks
    )

    # ----------
    # Plot 4: timeseries of % of idle CPU cores
    # ----------

    plot_elastic_results(
        "ts_vcpus",
        results,
        ax4,
        timeseries_num_vms=timeseries_num_vms,
        timeseries_num_tasks=timeseries_num_tasks
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "elastic")
