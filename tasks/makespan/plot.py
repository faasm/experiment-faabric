from invoke import task
from matplotlib.pyplot import subplots
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
