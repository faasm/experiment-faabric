from base64 import b64encode
from glob import glob
from os.path import join
from pandas import read_csv
from tasks.util.env import EXAMPLES_DOCKER_DIR, PLOTS_ROOT, RESULTS_DIR
from tasks.util.math import cum_sum
from tasks.util.plot import (
    fix_hist_step_vertical_line_at_end,
    get_color_for_baseline,
    get_label_for_baseline,
)
from tasks.util.trace import load_task_trace_from_file

# TODO: move this constants to a shared makesan file (right now they live
# in util/makespan)
MAKESPAN_RESULTS_DIR = join(RESULTS_DIR, "makespan")
NATIVE_BASELINES = ["batch", "slurm"]

ELASTIC_RESULTS_DIR = join(RESULTS_DIR, "elastic")
ELASTIC_PLOTS_DIR = join(PLOTS_ROOT, "elastic")

OPENMP_ELASTIC_USER = "omp-elastic"
OPENMP_ELASTIC_FUNCTION = "main"

# This is the ParRes Kernel that we use for the elastic experiment. Possible
# candidates are:
# - sparse: long running and good scaling
# - p2p: better scaling than sparse, but shorter running
ELASTIC_KERNEL = "p2p"

ELASTIC_KERNELS_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "Kernels-elastic")
ELASTIC_KERNELS_WASM_DIR = join(ELASTIC_KERNELS_DOCKER_DIR, "build", "wasm")
ELASTIC_KERNELS_NATIVE_DIR = join(ELASTIC_KERNELS_DOCKER_DIR, "build", "native")

OPENMP_ELASTIC_WASM = join(ELASTIC_KERNELS_WASM_DIR, "omp_{}.wasm".format(ELASTIC_KERNEL))
OPENMP_ELASTIC_NATIVE_BINARY = join(ELASTIC_KERNELS_NATIVE_DIR, "omp_{}.o".format(ELASTIC_KERNEL))

# Parameters for the macrobenchmark
OPENMP_ELASTIC_NUM_LOOPS = 5


def get_elastic_input_data(num_loops=OPENMP_ELASTIC_NUM_LOOPS, native=False):
    if native:
        return "FAASM_BENCH_PARAMS={}".format(int(num_loops))

    return b64encode("{}".format(int(num_loops)).encode("utf-8")).decode("utf-8")


def read_elastic_results(num_vms, num_tasks, num_cpus_per_vm):
    result_dict = {}

    # -----
    # Results to visualise makespan
    # -----

    glob_str = "makespan_makespan_*_{}_omp-elastic_{}_{}.csv".format(
        num_vms, num_tasks, num_cpus_per_vm
    )
    for csv in glob(join(MAKESPAN_RESULTS_DIR, glob_str)):
        baseline = csv.split("_")[2]
        results = read_csv(csv)
        result_dict[baseline] = {}

        makespan_s = results["MakespanSecs"].to_list()
        assert len(makespan_s) == 1, "Too many rows: expected 1, got {}!".format(len(makespan_s))
        makespan_s = makespan_s[0]
        result_dict[baseline]["makespan"] = makespan_s

        print(
            "Num VMs: {} - Num Tasks: {} - Baseline: {} - Makespan: {}s".format(
                num_vms, num_tasks, baseline, makespan_s
            )
        )

    # -----
    # Results to visualize all the rest
    # -----

    glob_str = "makespan_exec-task-info_*_{}_omp-elastic_{}_{}.csv".format(
        num_vms, num_tasks, num_cpus_per_vm
    )
    for csv in glob(join(MAKESPAN_RESULTS_DIR, glob_str)):
        baseline = csv.split("_")[2]
        results = read_csv(csv)

        # -----
        # Results to visualise JCT
        # -----

        task_ids = results["TaskId"].to_list()
        start_ts = results["StartTimeStamp"].to_list()
        genesis_ts = min(start_ts)

        result_dict[baseline]["exec-time"] = [-1 for _ in task_ids]
        result_dict[baseline]["queue-time"] = [-1 for _ in task_ids]
        result_dict[baseline]["jct"] = [-1 for _ in task_ids]

        times_exec = results["TimeExecuting"].to_list()
        times_queue = results["TimeInQueue"].to_list()
        end_ts = results["EndTimeStamp"].to_list()
        for tid, texec, tqueue, e_ts in zip(
            task_ids, times_exec, times_queue, end_ts
        ):
            result_dict[baseline]["exec-time"][tid] = texec
            result_dict[baseline]["queue-time"][tid] = tqueue
            result_dict[baseline]["jct"][tid] = e_ts - genesis_ts

        # ----
        # Results to visualise % of idle CPU cores (and time-series)
        # -----

        time_elapsed_secs = int(results.max()["EndTimeStamp"] - genesis_ts)
        tasks_per_ts = [[] for i in range(time_elapsed_secs)]

        for index, row in results.iterrows():
            task_id = row["TaskId"]
            start_slot = int(row["StartTimeStamp"] - genesis_ts)
            end_slot = int(row["EndTimeStamp"] - genesis_ts)

            for ind in range(start_slot, end_slot):
                tasks_per_ts[ind].append(task_id)

        for tasks in tasks_per_ts:
            tasks.sort()

        tasks_per_ts = {ts: tasks for ts, tasks in enumerate(tasks_per_ts)}

        result_dict[baseline]["tasks_per_ts"] = tasks_per_ts

        # -----
        # Results to visualise % of idle CPU cores (and time-series)
        # -----

        task_trace = load_task_trace_from_file(
            "omp-elastic", num_tasks, num_cpus_per_vm
        )

        result_dict[baseline]["ts_vcpus"] = {}
        total_available_vcpus = num_vms * num_cpus_per_vm
        sched_info_csv = "makespan_sched-info_{}_{}_omp-elastic_{}_{}.csv".format(
                baseline, num_vms, num_tasks, num_cpus_per_vm
        )

        if baseline in NATIVE_BASELINES:
            # First, set each timestamp to the total available vCPUs
            for ts in result_dict[baseline]["tasks_per_ts"]:
                result_dict[baseline]["ts_vcpus"][ts] = total_available_vcpus

            # Second, for each ts subtract the size of each task in-flight
            for ts in result_dict[baseline]["tasks_per_ts"]:
                for t in result_dict[baseline]["tasks_per_ts"][ts]:
                    result_dict[baseline]["ts_vcpus"][ts] -= task_trace[
                        int(t)
                    ].size

            # Third, express the results as percentages, and the number of
            # idle VMs as a number (not as a set)
            for ts in result_dict[baseline]["ts_vcpus"]:
                result_dict[baseline]["ts_vcpus"][ts] = (
                    result_dict[baseline]["ts_vcpus"][ts] / total_available_vcpus
                ) * 100
        else:
            # For Granny, the idle vCPUs results are directly available in
            # the file
            sch_info_csv = read_csv(join(MAKESPAN_RESULTS_DIR, sched_info_csv))
            idle_cpus = (sch_info_csv["NumIdleCpus"] / total_available_vcpus * 100).to_list()
            tss = (sch_info_csv["TimeStampSecs"] - sch_info_csv["TimeStampSecs"][0]).to_list()

            # Idle vCPUs
            for (idle_cpu, ts) in zip(idle_cpus, tss):
                result_dict[baseline]["ts_vcpus"][ts] = idle_cpu

    return result_dict


def _do_plot_makespan(results, ax, **kwargs):
    assert "num_vms" in kwargs, "num_vms not in kwargs!"
    assert "num_tasks" in kwargs, "num_tasks not in kwargs!"
    num_vms = kwargs["num_vms"]
    num_tasks = kwargs["num_tasks"]

    baselines = ["batch", "slurm", "granny", "granny-elastic"]

    xs = []
    ys = []
    colors = []
    xticks = []
    xticklabels = []

    for ind, n_vms in enumerate(num_vms):
        x_offset = ind * len(baselines) + (ind + 1)
        xs += [x + x_offset for x in range(len(baselines))]
        ys += [
            results[n_vms][baseline]["makespan"] for baseline in baselines
        ]
        colors += [
            get_color_for_baseline("omp-elastic", baseline)
            for baseline in baselines
        ]

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
    ax.set_ylabel("Makespan [s]")

    ax.set_xticks(xticks, labels=xticklabels, fontsize=6)


def _do_plot_cdf_jct(results, ax, **kwargs):
    assert "cdf_num_vms" in kwargs, "cdf_num_vms not in kwargs!"
    assert "cdf_num_tasks" in kwargs, "cdf_num_tasks not in kwargs!"
    cdf_num_vms = kwargs["cdf_num_vms"]
    cdf_num_tasks = kwargs["cdf_num_tasks"]

    baselines = ["slurm", "batch", "granny", "granny-elastic"]

    xs = list(range(cdf_num_tasks))
    for baseline in baselines:
        ys = []

        # Calculate the histogram using the histogram function, get the
        # results from the return value, but make the plot transparent.
        # TODO: maybe just calculate the CDF analitically?
        ys, xs, patches = ax.hist(
            results[cdf_num_vms][baseline]["jct"],
            100,
            color=get_color_for_baseline("omp-elastic", baseline),
            label=get_label_for_baseline("omp-elastic", baseline),
            histtype="step",
            density=True,
            cumulative=True,
        )
        fix_hist_step_vertical_line_at_end(ax)

        # Interpolate more points
        # spl = splrep(xs[:-1], ys, s=0.01, per=False)
        # x2 = linspace(xs[0], xs[-1], 400)
        # y2 = splev(x2, spl)
        # ax.plot(x2, y2, color=PLOT_COLORS[label], label=this_label, linewidth=0.5)

        ax.set_xlabel("Job Completion Time [s]")
        ax.set_ylabel("CDF")
        ax.set_ylim(bottom=0, top=1)


def _do_plot_percentage_vcpus(results, ax, **kwargs):
    assert "num_vms" in kwargs, "num_vms not in kwargs!"
    assert "num_tasks" in kwargs, "num_tasks not in kwargs!"
    assert "num_cpus_per_vm" in kwargs, "num_cpus_per_vm not in kwargs!"
    num_vms = kwargs["num_vms"]
    num_tasks = kwargs["num_tasks"]
    num_cpus_per_vm = kwargs["num_cpus_per_vm"]

    baselines = ["slurm", "batch", "granny", "granny-elastic"]

    xs = []
    ys = []
    xticklabels = []

    # Integral of idle CPU cores over time
    cumsum_ys = {}
    for baseline in baselines:
        cumsum_ys[baseline] = {}

        for n_vms in num_vms:
            timestamps = list(results[n_vms][baseline]["ts_vcpus"].keys())
            total_cpusecs = (timestamps[-1] - timestamps[0]) * num_cpus_per_vm * int(n_vms)

            cumsum = cum_sum(
                timestamps,
                [res * num_cpus_per_vm * int(n_vms) / 100
                    for res in list(results[n_vms][baseline]["ts_vcpus"].values())],
            )

            # Record both the total idle CPUsecs and the percentage
            cumsum_ys[baseline][n_vms] = (cumsum, (cumsum / total_cpusecs) * 100)

    xs = [ind for ind in range(len(num_vms))]
    xticklabels = []

    for (n_vms, n_tasks) in zip(num_vms, num_tasks):
        xticklabels.append(
            "{} VMs\n({} Jobs)".format(n_vms, n_tasks)
        )
    for baseline in baselines:
        ys = [cumsum_ys[baseline][n_vms][1] for n_vms in num_vms]
        ax.plot(
            xs,
            ys,
            color=get_color_for_baseline("omp-elastic", baseline),
            label=get_label_for_baseline("omp-elastic", baseline),
            linestyle="-",
            marker=".",
        )

    ax.set_ylim(bottom=0)
    ax.set_xlim(left=-0.25)
    ax.set_ylabel("Idle CPU-seconds /\n Total CPU-seconds [%]", fontsize=8)
    ax.set_xticks(xs, labels=xticklabels, fontsize=6)


def _do_plot_ts_vcpus(results, ax, **kwargs):
    assert "timeseries_num_vms" in kwargs, "timeseries_num_vms not in kwargs!"
    assert "timeseries_num_tasks" in kwargs, "timeseries_num_tasks not in kwargs!"
    num_vms = kwargs["timeseries_num_vms"]

    baselines = ["slurm", "batch", "granny-elastic"]
    xlim = 0
    for baseline in baselines:
        if baseline in NATIVE_BASELINES:
            xs = range(len(results[num_vms][baseline]["ts_vcpus"]))
        else:
            xs = list(results[num_vms][baseline]["ts_vcpus"].keys())
        xlim = max(xlim, max(xs))

        ax.plot(
            xs,
            [results[num_vms][baseline]["ts_vcpus"][x] for x in xs],
            label=get_label_for_baseline("omp-elastic", baseline),
            color=get_color_for_baseline("omp-elastic", baseline),
        )

    ax.set_xlim(left=0, right=xlim)
    ax.set_ylim(bottom=0, top=100)
    ax.set_ylabel("% idle vCPUs")
    ax.set_xlabel("Time [s]")


def plot_elastic_results(plot_name, results, ax, **kwargs):
    if plot_name == "makespan":
        _do_plot_makespan(results, ax, **kwargs)
    elif plot_name == "cdf_jct":
        _do_plot_cdf_jct(results, ax, **kwargs)
    elif plot_name == "percentage_vcpus":
        _do_plot_percentage_vcpus(results, ax, **kwargs)
    elif plot_name == "ts_vcpus":
        _do_plot_ts_vcpus(results, ax, **kwargs)
