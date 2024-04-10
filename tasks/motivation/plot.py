from invoke import task
from matplotlib.pyplot import subplots
from os import makedirs
from os.path import join
from tasks.util.env import PLOTS_ROOT
from tasks.util.makespan import do_makespan_plot, read_makespan_results
from tasks.util.plot import save_plot

MOTIVATION_PLOTS_DIR = join(PLOTS_ROOT, "motivation")


@task(default=True)
def plot(ctx):
    """
    Plot the motivation figure illustrating the trade-off between locality and
    utilisation
    """
    # num_vms = [16, 24, 32, 48, 64]
    # num_tasks = [50, 75, 100, 150, 200]
    num_vms = 16
    num_tasks = 50
    num_cpus_per_vm = 8

    results = {}
    results[num_vms] = read_makespan_results(num_vms, num_tasks, num_cpus_per_vm)
    makedirs(MOTIVATION_PLOTS_DIR, exist_ok=True)

    # ----------
    # Plot 1: timeseries of the percentage of idle vCPUs
    # ----------

    fig, ax1 = subplots(figsize=(6, 3))
    do_makespan_plot("ts_vcpus", results, ax1, num_vms, num_tasks)
    ax1.legend()
    save_plot(fig, MOTIVATION_PLOTS_DIR, "motivation_vcpus")

    # ----------
    # Plot 2: timeseries of the number of cross-VM links
    # ----------

    fig, ax2 = subplots(figsize=(6, 3))
    do_makespan_plot("ts_xvm_links", results, ax2, num_vms, num_tasks)
    save_plot(fig, MOTIVATION_PLOTS_DIR, "motivation_xvm_links")
