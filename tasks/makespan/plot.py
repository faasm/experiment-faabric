from invoke import task
from matplotlib.pyplot import subplots, subplot_mosaic
from tasks.util.makespan import (
    MAKESPAN_PLOTS_DIR,
    do_makespan_plot,
    read_makespan_results,
)
from tasks.util.plot import save_plot


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
def conservative(ctx):
    """
    Macrobenchmark plot showing the benefits of migrating MPI applications to
    improve locality of execution. We show:
    - LHS: box plot of idle vCPUs and # of cross-VM links for all VM sizes
    - RHS: timeseries of one of the box plots
    """
    # NOTE: probably we want highter num-tasks here to make sure we migrate
    # more
    # num_vms = [16, 24, 32, 48, 64]
    # num_tasks = [50, 75, 100, 150, 200]
    num_vms = [8, 16, 24]
    num_tasks = [25, 50, 75]
    num_cpus_per_vm = 8

    # RHS: zoom in one of the bars
    timeseries_num_vms = 16 # 32
    timeseries_num_tasks = 50 # 100

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
    - LHS: Bar plot of the VMseconds used per execution
    - RHS: timeseries of the number of idle VMs over time
    """
    # NOTE: probably we want lower num-tasks here to just show the benefits
    # at the tails
    # num_vms = [16, 24, 32, 48, 64]
    # num_tasks = [50, 75, 100, 150, 200]
    num_vms = [8, 16, 24]
    num_tasks = [25, 50, 75]
    num_cpus_per_vm = 8

    # RHS: zoom in one of the bars
    timeseries_num_vms = 16 # 32
    timeseries_num_tasks = 50 # 100

    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_makespan_results(n_vms, n_tasks, num_cpus_per_vm)

    fig, ax = subplot_mosaic([['left', 'right'],
                              ['left', 'right']])

    # ----------
    # Plot 1: bar plot of the CPUsecs per execution
    # ----------

    do_makespan_plot(
        "used_vmsecs",
        results,
        ax["left"],
        num_vms,
        num_tasks
    )

    # ----------
    # Plot 2: timeseries of one of the cluster sizes
    # ----------

    do_makespan_plot(
        "ts_idle_vms",
        results,
        ax["right"],
        timeseries_num_vms,
        timeseries_num_tasks
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "idle_vms")
