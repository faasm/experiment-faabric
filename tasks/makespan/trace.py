from invoke import task
from numpy import arange
from numpy.random import default_rng
from random import uniform
from tasks.makespan.data import TaskObject
from tasks.util.makespan import MPI_WORKLOADS
from tasks.util.trace import dump_task_trace_to_file
from typing import List


@task()
def generate(ctx, workload, num_tasks, num_cores_per_vm, lmbd="0.1"):
    """
    A trace is a set of tasks where each task is identified by:
    - An arrival time sampled from a Poisson distribution with parameter lambda
    - A size (from half a VM to two VMs)
    - A user (from a set of users)

    Instead of arrival times, we use inter-arrival times, so in the trace we
    record the time it takes for the task to be arrive wrt the previous task.
    We use that if arrival times are a Possion(lambda), then inter-arrival
    times are an exponential with parameter 1/lambda.
    """
    num_tasks = int(num_tasks)
    num_cores_per_vm = int(num_cores_per_vm)
    lmbd = float(lmbd)

    # Work out the possible number of cores per VM
    # possible_mpi_sizes = arange(2, int(num_cores_per_vm * 2))
    if workload == "mpi-evict" or workload == "mpi-spot":
        possible_mpi_sizes = arange(4, int(num_cores_per_vm * 2))
    else:
        possible_mpi_sizes = arange(2, int(num_cores_per_vm * 2))
    possible_omp_sizes = arange(1, num_cores_per_vm)

    # The lambda parameter regulates how frequently new tasks arrive. If we
    # make lambda smaller, then tasks will be more far apart. Formally, the
    # lambda parameter is the inverse of the expected inter-arrival time
    # lmbd = 0.1 is fine for 4 VMs w/ 4 cores per VM
    exp_mean = 1 / lmbd
    rng = default_rng()
    inter_arrival_times = [
        int(i) for i in rng.exponential(exp_mean, int(num_tasks) - 1)
    ]
    inter_arrival_times.insert(0, 0)

    # Work out the possible different workloads
    if workload == "mpi":
        possible_workloads = ["mpi"]
    elif workload == "mpi-migrate":
        possible_workloads = ["mpi-migrate"]
    elif workload == "mpi-evict":
        possible_workloads = ["mpi-migrate"]
    elif workload == "mpi-spot":
        possible_workloads = ["mpi-migrate"]
    elif workload == "omp":
        possible_workloads = ["omp"]
    elif workload == "mix":
        possible_workloads = ["mpi", "omp"]
    else:
        raise RuntimeError("Unrecognised workload: {}".format(workload))

    # Generate the random task trace
    task_trace: List[TaskObject] = []
    num_pos_wl = len(possible_workloads)
    for idx in range(num_tasks):
        wl_idx = int(uniform(0, num_pos_wl))
        if possible_workloads[wl_idx] in MPI_WORKLOADS:
            possible_sizes = possible_mpi_sizes
        elif possible_workloads[wl_idx] == "omp":
            possible_sizes = possible_omp_sizes
        ws_idx = int(uniform(0, len(possible_sizes)))
        task_trace.append(
            TaskObject(
                idx,
                possible_workloads[wl_idx],
                possible_sizes[ws_idx],
                inter_arrival_times[idx],
            )
        )

    dump_task_trace_to_file(task_trace, workload, num_tasks, num_cores_per_vm)
