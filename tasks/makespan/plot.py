from invoke import task
from matplotlib.pyplot import subplots, subplot_mosaic
# TODO: consider moving some of the migration to a different file
from tasks.util.makespan import (
    MAKESPAN_PLOTS_DIR,
    do_makespan_plot,
    read_makespan_results,
)
from tasks.util.eviction import (
        read_eviction_results,
        plot_eviction_results,
)
from tasks.util.plot import save_plot
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
    timeseries_num_vms = 16
    timeseries_num_tasks = 100

    # WARN: this assumes that we never repeat num_vms with different numbers of
    # num_tasks (fair at this point)
    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_makespan_results(n_vms, n_tasks, num_cpus_per_vm)

    fig, ax = subplot_mosaic([['upper left', 'upper right'],
                              ['lower left', 'lower right']])

    # ----------
    # Plot 1: boxplot of idle vCPUs and num xVM links for various cluster sizes
    # ----------

    do_makespan_plot(
        "boxplot_vcpus",
        results,
        ax["upper left"],
        num_vms,
        num_tasks
    )

    do_makespan_plot(
        "percentage_xvm",
        results,
        ax["lower left"],
        num_vms,
        num_tasks
    )

    # ----------
    # Plot 2: (two) timeseries of one of the cluster sizes
    # ----------

    do_makespan_plot(
        "ts_vcpus",
        results,
        ax["upper right"],
        timeseries_num_vms,
        timeseries_num_tasks
    )

    do_makespan_plot(
        "ts_xvm_links",
        results,
        ax["lower right"],
        timeseries_num_vms,
        timeseries_num_tasks
    )

    # ax[0][0].legend()
    save_plot(fig, MAKESPAN_PLOTS_DIR, "resource_usage")


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
