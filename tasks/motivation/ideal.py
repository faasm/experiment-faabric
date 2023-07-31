from glob import glob
from invoke import task
from matplotlib.patches import Patch
from matplotlib.pyplot import subplots
from os import makedirs
from os.path import join
from pandas import read_csv
from random import randint
from tasks.lammps.env import get_faasm_benchmark
from tasks.makespan.env import (
    LAMMPS_DOCKER_BINARY,
    LAMMPS_DOCKER_DIR,
)
from tasks.util.env import PLOTS_ROOT, RESULTS_DIR
from tasks.util.openmpi import get_native_mpi_pods, run_kubectl_cmd
from time import time


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "motivation")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("Size,CrossVMLinks,ExecutionTimeSecs\n")

    return result_file


def _write_csv_line(csv_name, size, num_links, exec_time):
    result_dir = join(RESULTS_DIR, "motivation")
    result_file = join(result_dir, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{:.2f}\n".format(size, num_links, exec_time))


def partition(number):
    """
    Given a whole number, find all its partitions (equivalently, these are all
    the ways an application can be deployed)
    """
    answer = set()
    answer.add((number, ))
    for x in range(1, number):
        for y in partition(number - x):
            to_add = tuple(sorted((x, ) + y))
            if max(to_add) > 8:
                continue
            answer.add(to_add)

    return answer


def vm_links_from_partition(partition):
    """
    Given a partition of an application, return the number of cross-VM links
    """
    # If we are deployed in one single node, the number of links is 0
    if len(partition) == 1:
        return 0

    # Otherwise, the number of links is the product of the number of processes
    # in each VM
    links = partition[0]
    for i in range(1, len(partition)):
        links = links * partition[i]

    return links


def do_single_run(vm_names, vm_ips, size, partition):
    """
    Given the size and the partition, execute a simulation with that size and
    partition and return the execution time
    """
    # Prepare IP allocation
    allocated_pod_ips = []
    pod_idx = 0
    for num_in_pod in partition:
        for _ in range(num_in_pod):
            allocated_pod_ips.append(vm_ips[pod_idx])
        pod_idx += 1
    assert len(allocated_pod_ips) == size

    # Prepare LAMMPS command line
    data_file = get_faasm_benchmark("compute-xl")["data"][0]
    lammps_cmdline = "-in {}/{}.faasm.native".format(LAMMPS_DOCKER_DIR, data_file)

    # Prepare mpirun command
    mpirun_cmd = [
        "mpirun",
        "-np {}".format(size),
        # We are explicit about the host distribution to force the partition
        "-host {}".format(",".join(allocated_pod_ips)),
        LAMMPS_DOCKER_BINARY,
        lammps_cmdline,
    ]
    mpirun_cmd = " ".join(mpirun_cmd)

    # Prepare exec command (note that we need to use the VM name to exec into
    # it)
    exec_cmd = [
        "exec",
        vm_names[0],
        "--",
        "su mpirun -c '{}'".format(mpirun_cmd),
    ]
    exec_cmd = " ".join(exec_cmd)

    # Run it and return the time elapsed
    start_ts = time()
    run_kubectl_cmd("lammps", exec_cmd)
    return time() - start_ts


@task()
def run(ctx, size=None):
    vm_names, vm_ips = get_native_mpi_pods("lammps")
    assert len(vm_ips) == 16

    if not size:
        # sizes = range(4, 16)
        sizes = range(9, 16)
    else:
        sizes = [int(size)]

    for sz in sizes:
        csv_name = "ideal_crossvm_times_{}.csv".format(sz)
        _init_csv_file(csv_name)

        size_permutations = partition(sz)
        for size_permutation in size_permutations:
            exec_time = do_single_run(vm_names, vm_ips, sz, size_permutation)
            _write_csv_line(csv_name, sz, vm_links_from_partition(size_permutation), exec_time)


@task
def combine_csv(ctx):
    """
    Combine all ideal_crossvm_times_*.csv files in one single file, sorted by
    size, and number of cross vm links
    """
    results_dir = join(RESULTS_DIR, "motivation")
    glob_str = "ideal_crossvm_times_*"
    csv_files = glob(join(results_dir, glob_str))
    csv_files = sorted(csv_files, key=lambda fn: int(fn.split("_")[-1][0:-4]))

    out_file = join(results_dir, "ideal_crossvm_times.csv")
    first = True
    for csv_file in csv_files:
        df = read_csv(csv_file)
        df = df.sort_values(by=["CrossVMLinks"])

        if first:
            df.to_csv(out_file, mode="w", index=False)
            first = False
            continue

        df.to_csv(out_file, mode="a", header=False, index=False)


@task
def plot_correlation(ctx):
    results_dir = join(RESULTS_DIR, "motivation")
    data_file = join(results_dir, "ideal_crossvm_times.csv")

    pd = read_csv(data_file)

    # Generate random colors
    colors = []
    for i in range(16):
        colors.append('#%06X' % randint(0, 0xFFFFFF))

    # Assign each point a color depending on the world size
    point_col = [colors[i] for i in pd["Size"]]

    # For each diferent world size, create a legend entry with the corresponding
    # color
    legend_handles = []
    point_labels = set([i for i in pd["Size"]])
    for pl in point_labels:
        legend_handles.append(Patch(color=colors[pl], label=str(pl)))

    fig, ax = subplots()
    ax.scatter(pd["CrossVMLinks"], pd["ExecutionTimeSecs"], c=point_col)
    ax.set_xlabel("# cross-VM links")
    ax.set_ylabel("Execution Time [s]")
    ax.legend(handles=legend_handles)

    plot_file = join(PLOTS_ROOT, "motivation", "xvm_correlation.pdf")
    fig.savefig(plot_file)
