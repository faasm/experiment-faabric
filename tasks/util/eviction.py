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
from tasks.util.plot import get_color_for_baseline, get_label_for_baseline

MAKESPAN_RESULTS_DIR = join(RESULTS_DIR, "makespan")
MAKESPAN_PLOTS_DIR = join(PLOTS_ROOT, "makespan")


def get_user_id_from_task_id(num_tasks_per_user, task_id):
    return int(task_id / num_tasks_per_user) + 1


def read_eviction_results(num_vms, num_users, num_tasks, num_cpus_per_vm):
    result_dict = {}

    num_tasks_per_user = int(num_tasks / num_users)
    glob_str = (
        "makespan_exec-task-info_*_{}vms_{}tpusr_mpi-evict_{}_{}.csv".format(
            num_vms, num_tasks_per_user, num_tasks, num_cpus_per_vm
        )
    )
    for csv in glob(join(MAKESPAN_RESULTS_DIR, glob_str)):
        baseline = csv.split("_")[2]
        results = read_csv(csv)
        result_dict[baseline] = {}

        # -----
        # Results to visualise makespan
        # -----

        start_ts = results.min()["StartTimeStamp"]
        end_ts = results.max()["EndTimeStamp"]
        time_elapsed_secs = int(end_ts - start_ts)
        result_dict[baseline]["makespan"] = time_elapsed_secs
        print(
            "Num VMs: {} - Num Users: {} - Num Tasks: {} -"
            " Baseline: {} - Makespan: {}s".format(
                num_vms, num_users, num_tasks, baseline, time_elapsed_secs
            )
        )

        # -----
        # Results to visualise # active jobs per user
        # -----

        if time_elapsed_secs > 1e5:
            raise RuntimeError(
                "Measured total time elapsed is too long: {}".format(
                    time_elapsed_secs
                )
            )

        result_dict[baseline]["tasks_per_user_per_ts"] = {}
        for ts in range(time_elapsed_secs):
            result_dict[baseline]["tasks_per_user_per_ts"][ts] = {}
            for uid in range(num_users):
                result_dict[baseline]["tasks_per_user_per_ts"][ts][uid] = 0

        for index, row in results.iterrows():
            task_id = row["TaskId"]
            user_id = get_user_id_from_task_id(num_tasks_per_user, task_id) - 1
            start_slot = int(row["StartTimeStamp"] - start_ts)
            end_slot = int(row["EndTimeStamp"] - start_ts)
            for ind in range(start_slot, end_slot):
                if (
                    user_id
                    not in result_dict[baseline]["tasks_per_user_per_ts"]
                ):
                    print("User {} not registered in results!".format(user_id))
                    raise RuntimeError("User not registered!")

                result_dict[baseline]["tasks_per_user_per_ts"][ind][
                    user_id
                ] += 1

    return result_dict


def _do_plot_makespan(results, ax, **kwargs):
    assert "num_vms" in kwargs, "num_vms not in kwargs!"
    assert "num_tasks" in kwargs, "num_tasks not in kwargs!"
    assert "num_users" in kwargs, "num_users not in kwargs!"
    num_vms = kwargs["num_vms"]
    num_tasks = kwargs["num_tasks"]
    num_users = kwargs["num_users"]

    # labels = ["slurm", "batch", "granny", "granny-migrate"]
    labels = ["slurm", "batch", "granny-migrate"]

    xs = []
    ys = []
    colors = []
    xticks = []
    xticklabels = []

    # WARNING: this plot reads num_vms as an array
    for ind, n_vms in enumerate(num_vms):
        x_offset = ind * len(labels) + (ind + 1)
        xs += [x + x_offset for x in range(len(labels))]
        ys += [results[n_vms][la]["makespan"] for la in labels]
        colors += [get_color_for_baseline("mpi-migrate", la) for la in labels]

        # Add one tick and xlabel per VM size
        xticks.append(x_offset + len(labels) / 2)
        xticklabels.append(
            "{} VMs\n({} Jobs - {} Users)".format(
                n_vms, num_tasks[ind], num_users[ind]
            )
        )

        # Add spacing between vms
        xs.append(x_offset + len(labels))
        ys.append(0)
        colors.append("white")

    ax.bar(xs, ys, color=colors, edgecolor="black", width=1)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Makespan [s]")
    ax.set_xticks(xticks, labels=xticklabels, fontsize=6)

    # Manually craft legend
    legend_entries = [
        Patch(
            color=get_color_for_baseline("mpi-migrate", label),
            label=get_label_for_baseline("mpi-migrate", label),
        )
        for label in labels
    ]
    ax.legend(handles=legend_entries, ncols=2, fontsize=8)


def _do_plot_tasks_per_user(results, ax, **kwargs):
    """
    Plot the time series of the number of active jobs per user. We will make
    a different line for each different user, but all lines from the same
    baseline in the same color
    """
    # Here these variables are a single value, not a list!
    assert "num_users" in kwargs, "num_users not in kwargs!"
    assert "num_vms" in kwargs, "num_vms not in kwargs!"
    num_users = kwargs["num_users"]
    num_vms = kwargs["num_vms"]

    # baselines = ["slurm", "batch", "granny", "granny-migrate"]
    baselines = ["slurm", "batch", "granny-migrate"]
    xs = {}
    for baseline in baselines:
        xs[baseline] = list(
            results[num_vms][baseline]["tasks_per_user_per_ts"].keys()
        )

    # For each baseline, for each user id, plot the timeseries of active jobs
    num_points_spline = 500
    for baseline in baselines:
        for user_id in range(num_users):
            ys = [
                results[num_vms][baseline]["tasks_per_user_per_ts"][x][user_id]
                for x in xs[baseline]
            ]
            ax.plot(
                xs[baseline],
                ys,
                color=get_color_for_baseline("mpi-migrate", baseline),
                linestyle="dotted",
            )

            spline = CubicSpline(xs[baseline], ys)
            xs_spline = linspace(0, max(xs[baseline]), num=num_points_spline)
            ax.plot(
                xs_spline,
                spline(xs_spline),
                color=get_color_for_baseline("mpi-migrate", baseline),
                linestyle="-",
            )


def plot_eviction_results(plot_name, results, ax, **kwargs):
    if plot_name == "makespan":
        _do_plot_makespan(results, ax, **kwargs)
    elif plot_name == "tasks_per_user":
        _do_plot_tasks_per_user(results, ax, **kwargs)
    else:
        raise RuntimeError("Unrecognised plot name: {}".format(plot_name))
