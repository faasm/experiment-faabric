from faasmctl.util.config import get_faasm_worker_ips
from faasmctl.util.planner import reset as reset_planner
from invoke import task
from os import makedirs
from os.path import basename, join
from tasks.util.env import RESULTS_DIR
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from tasks.util.lammps import (
    LAMMPS_FAASM_USER,
    LAMMPS_MIGRATION_NET_DOCKER_BINARY,
    LAMMPS_MIGRATION_NET_DOCKER_DIR,
    LAMMPS_FAASM_MIGRATION_NET_FUNC,
    LAMMPS_SIM_WORKLOAD,
    get_faasm_benchmark,
    get_lammps_migration_params,
)
from tasks.util.openmpi import (
    get_native_mpi_pods,
    run_kubectl_cmd,
)
from time import sleep, time

# Parameters tuning the experiment runs
NPROCS_EXPERIMENT = [2, 4, 8, 12, 16]


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "lammps")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("WorldSize,Run,Time\n")

    return result_file


def _write_csv_line(csv_name, nprocs, run_num, actual_time):
    result_dir = join(RESULTS_DIR, "lammps")
    result_file = join(result_dir, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{:.2f}\n".format(nprocs, run_num, actual_time))


@task()
def granny(ctx, workload=LAMMPS_SIM_WORKLOAD, repeats=1):
    """
    Run LAMMPS simulation on Granny
    """
    csv_name = "lammps_granny_{}.csv".format(workload)
    _init_csv_file(csv_name)
    num_vms = len(get_faasm_worker_ips())
    assert num_vms == 2, "Expected 2 VMs got: {}!".format(num_vms)

    # Run multiple benchmarks if desired for convenience
    data_file = basename(get_faasm_benchmark(workload)["data"][0])
    for nproc in NPROCS_EXPERIMENT:
        reset_planner(num_vms)

        for nrep in range(repeats):
            print(
                "Running LAMMPS on Granny with {} MPI processes"
                " (workload: {}, run: {}/{})".format(
                    nproc, workload, nrep + 1, repeats
                )
            )

            # Run LAMMPS
            cmdline = "-in faasm://lammps-data/{}".format(data_file)
            msg = {
                "user": LAMMPS_FAASM_USER,
                "function": LAMMPS_FAASM_MIGRATION_NET_FUNC,
                "cmdline": cmdline,
                "mpi_world_size": int(nproc),
                "input_data": get_lammps_migration_params(num_net_loops=10000, chunk_size=20000),
            }
            result_json = post_async_msg_and_get_result_json(msg)
            actual_time = get_faasm_exec_time_from_json(result_json)
            _write_csv_line(csv_name, nproc, nrep, actual_time)


@task
def native(ctx, workload=LAMMPS_SIM_WORKLOAD, repeats=1):
    """
    Run LAMMPS experiment on OpenMPI
    """
    num_cpus_per_vm = 8
    num_vms = 2

    pod_names, pod_ips = get_native_mpi_pods("lammps")
    assert (
        len(pod_names) == num_vms and len(pod_ips) == num_vms
    ), "Not enough pods!"

    master_pod = pod_names[0]

    csv_name = "lammps_native_{}.csv".format(workload)
    _init_csv_file(csv_name)

    native_cmdline = "-in {}/{}.faasm.native".format(
        LAMMPS_MIGRATION_NET_DOCKER_DIR,
        get_faasm_benchmark(workload)["data"][0],
    )

    for nproc in NPROCS_EXPERIMENT:
        for nrep in range(repeats):
            print(
                "Running LAMMPS on native with {} MPI processes "
                "(workload: {}, run: {}/{})".format(
                    nproc, workload, nrep + 1, repeats
                )
            )

            # Prepare host list (in terms of IPs)
            if nproc > num_cpus_per_vm:
                host_list = [pod_ips[0]] * num_cpus_per_vm + [pod_ips[1]] * (
                    nproc - num_cpus_per_vm
                )
            else:
                host_list = [pod_ips[0]] * nproc

            # Prepare execution commands
            mpirun_cmd = [
                "mpirun",
                get_lammps_migration_params(native=True),
                "-np {}".format(nproc),
                "-host {}".format(",".join(host_list)),
                LAMMPS_MIGRATION_NET_DOCKER_BINARY,
                native_cmdline,
            ]
            mpirun_cmd = " ".join(mpirun_cmd)
            exec_cmd = [
                "exec",
                master_pod,
                "--",
                "su mpirun -c '{}'".format(mpirun_cmd),
            ]

            # Run command
            start = time()
            out = run_kubectl_cmd("lammps", " ".join(exec_cmd))
            print(out)
            end = time()
            actual_time = end - start
            _write_csv_line(csv_name, nproc, nrep, actual_time)

            sleep(2)
