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
from tasks.util.makespan import MAKESPAN_PLOTS_DIR
from tasks.util.locality import (
    plot_locality_results,
    read_locality_results,
)
from tasks.util.plot import (
    DOUBLE_COL_FIGSIZE_HALF,
    DOUBLE_COL_FIGSIZE_THIRD,
    get_color_for_baseline,
    get_label_for_baseline,
    save_plot,
)
from tasks.util.spot import (
    plot_spot_results,
    read_spot_results,
)


# TODO: delete me if miracle happens
@task
def migration(ctx):
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
    timeseries_num_vms = num_vms[-1]

    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_locality_results(
            n_vms, n_tasks, num_cpus_per_vm, migrate=True
        )

    # ----------
    # Plot 1: aggregate idle vCPUs
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "percentage_vcpus",
        results,
        ax,
        num_vms=num_vms,
        num_tasks=num_tasks,
        migrate=True,
    )

    # Manually craft the legend
    baselines = ["slurm", "batch", "granny", "granny-migrate"]
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
        ncols=2,
        bbox_to_anchor=(0.535, 0.3),
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_migrate_vcpus")

    # ----------
    # Plot 1: aggregate xVM links
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "percentage_xvm",
        results,
        ax,
        num_vms=num_vms,
        num_tasks=num_tasks,
        migrate=True,
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_migrate_xvm")

    # ----------
    # Plot 3: timeseries of vCPUs
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "ts_vcpus", results, ax, num_vms=timeseries_num_vms, migrate=True
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_migrate_ts_vcpus")

    # ----------
    # Plot 4: timeseries of xVM links
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "ts_xvm_links", results, ax, num_vms=timeseries_num_vms, migrate=True
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_migrate_ts_xvm")


@task
def locality(ctx):
    """
    Macrobenchmark plot showing the benefits of migrating MPI applications to
    improve locality of execution. We show:
    - LHS: both number of cross-VM links and number of idle cpu cores per exec
    - RHS: timeseries of one of the points in the plot
    """
    # num_vms = [8, 16, 24, 32]
    # num_tasks = [50, 100, 150, 200]
    # num_vms = [4, 8]
    # num_tasks = [10, 50]
    # num_vms = [8]
    # num_tasks = [50]
    num_vms = [8, 16, 24, 32]
    num_tasks = [25, 50, 75, 100]
    num_cpus_per_vm = 8

    # RHS: zoom in one of the bars
    timeseries_num_vms = num_vms[-1]
    timeseries_num_tasks = num_tasks[-1]

    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_locality_results(n_vms, n_tasks, num_cpus_per_vm)

    # ----------
    # Plot 1: makespan bar plot
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "makespan", results, ax, num_vms=num_vms, num_tasks=num_tasks
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_locality_makespan")

    # ----------
    # Plot 2: Aggregate vCPUs metric
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "percentage_vcpus", results, ax, num_vms=num_vms, num_tasks=num_tasks
    )

    # ----------
    # Plot 3: Aggregate xVM metric
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "percentage_xvm", results, ax, num_vms=num_vms, num_tasks=num_tasks
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_locality_xvm")

    # ----------
    # Plot 4: execution time CDF
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "cdf_jct",
        results,
        ax,
        cdf_num_vms=timeseries_num_vms,
        cdf_num_tasks=timeseries_num_tasks,
    )

    # Manually craft the legend
    baselines = ["granny-batch", "granny", "granny-migrate"]
    legend_entries = [
        Patch(
            color=get_color_for_baseline("mpi-locality", baseline),
            label=get_label_for_baseline("mpi-locality", baseline),
        )
        for baseline in baselines
    ]
    fig.legend(
        handles=legend_entries,
        loc="lower center",
        ncols=2,
        bbox_to_anchor=(0.65, 0.17),
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_locality_vcpus")

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_locality_cdf_jct")

    # ----------
    # Plot 5: time-series of idle vCPUs
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results("ts_vcpus", results, ax, num_vms=timeseries_num_vms)

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_locality_ts_vcpus")

    # ----------
    # Plot 5: time-series of cross-VM links
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_locality_results(
        "ts_xvm_links", results, ax, num_vms=timeseries_num_vms
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_locality_ts_xvm")


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
        results[n_vms] = read_eviction_results(
            n_vms, n_users, n_tasks, num_cpus_per_vm
        )

    fig, ax = subplot_mosaic([["left", "right"], ["left", "right"]])

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

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_HALF)

    # ----------
    # Plot 1: makespan slowdown (spot / no spot)
    # ----------

    plot_spot_results(
        "makespan",
        results,
        ax,
        num_vms=num_vms,
        num_tasks=num_tasks,
    )

    # Manually craft the legend
    baselines = ["slurm", "batch", "granny"]
    legend_entries = [
        Patch(
            color=get_color_for_baseline("mpi-spot", baseline),
            label=get_label_for_baseline("mpi-spot", baseline),
        )
        for baseline in baselines
    ]
    fig.legend(
        handles=legend_entries,
        loc="upper center",
        ncols=len(baselines),
        bbox_to_anchor=(0.52, 1.07),
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_spot_makespan")

    # ----------
    # Plot 2: stacked cost bar plot (spot) + real cost (no spot)
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_HALF)

    plot_spot_results(
        "cost",
        results,
        ax,
        num_vms=num_vms,
        num_tasks=num_tasks,
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_spot_cost")


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
    num_vms = [8, 16, 24, 32]
    num_tasks = [50, 100, 150, 200]
    num_cpus_per_vm = 8

    # RHS: zoom in one of the bars
    timeseries_num_vms = num_vms[-1]
    timeseries_num_tasks = num_tasks[-1]
    cdf_num_vms = timeseries_num_vms
    cdf_num_tasks = timeseries_num_tasks

    results = {}
    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        results[n_vms] = read_elastic_results(n_vms, n_tasks, num_cpus_per_vm)

    # ----------
    # Plot 1: makespan
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_elastic_results(
        "makespan",
        results,
        ax,
        num_vms=num_vms,
        num_tasks=num_tasks,
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_elastic_makespan")

    # ----------
    # Plot 2: percentage of idle vCPUs
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_elastic_results(
        "percentage_vcpus",
        results,
        ax,
        num_vms=num_vms,
        num_tasks=num_tasks,
        num_cpus_per_vm=num_cpus_per_vm,
    )

    # Manually craft the legend
    baselines = ["slurm", "batch", "granny", "granny-elastic"]
    legend_entries = [
        Patch(
            color=get_color_for_baseline("omp-elastic", baseline),
            label=get_label_for_baseline("omp-elastic", baseline),
        )
        for baseline in baselines
    ]
    fig.legend(
        handles=legend_entries,
        loc="lower center",
        ncols=2,
        bbox_to_anchor=(0.56, 0.2),
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_elastic_vcpus")

    # ----------
    # Plot 3: CDF of the JCT (for one run)
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_elastic_results(
        "cdf_jct",
        results,
        ax,
        cdf_num_vms=cdf_num_vms,
        cdf_num_tasks=cdf_num_tasks,
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_elastic_cdf_jct")

    # ----------
    # Plot 4: timeseries of % of idle CPU cores
    # ----------

    fig, ax = subplots(figsize=DOUBLE_COL_FIGSIZE_THIRD)

    plot_elastic_results(
        "ts_vcpus",
        results,
        ax,
        timeseries_num_vms=timeseries_num_vms,
        timeseries_num_tasks=timeseries_num_tasks,
    )

    save_plot(fig, MAKESPAN_PLOTS_DIR, "makespan_elastic_ts_vcpus")
