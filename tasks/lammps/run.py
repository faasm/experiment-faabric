from invoke import task
from os import environ, makedirs
from os.path import basename, join
from tasks.util.env import (
    LAMMPS_DOCKER_BINARY,
    LAMMPS_DOCKER_DATA_DIR,
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    get_faasm_planner_host_port,
    get_faasm_worker_ips,
    flush_workers as flush_planner_workers,
    post_async_msg_and_get_result_json,
    reset_planner,
    wait_for_workers as wait_for_planner_workers,
)
from tasks.util.openmpi import (
    NATIVE_HOSTFILE,
    get_native_mpi_pods,
    run_kubectl_cmd,
)
from tasks.lammps.env import (
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_FUNC,
    get_faasm_benchmark,
)
from time import time

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
def granny(ctx, data="compute-xl", repeats=1):
    """
    Run LAMMPS simulation on Granny
    """
    host, port = get_faasm_planner_host_port()
    url = "http://{}:{}".format(host, port)
    num_workers = len(get_faasm_worker_ips())

    wasm_vm = "wavm"
    if "WASM_VM" in environ:
        wasm_vm = environ["WASM_VM"]
    csv_name = "lammps_{}.csv".format(wasm_vm)
    _init_csv_file(csv_name)

    # Reset the planner and wait for the workers to register with it
    reset_planner()
    wait_for_planner_workers(num_workers)

    # Run multiple benchmarks if desired for convenience
    data_file = basename(get_faasm_benchmark(data)["data"][0])
    for nproc in [16]:  # NPROCS_EXPERIMENT:
        print(
            "Running LAMMPS on Granny with {} MPI processes (data: {})".format(
                nproc, data
            )
        )

        for nrep in range(repeats):
            # First, flush the host state
            print("Flushing functions, state, and shared files from workers")
            flush_planner_workers()

            # Run LAMMPS
            cmdline = "-in faasm://lammps-data/{}".format(data_file)
            msg = {
                "user": LAMMPS_FAASM_USER,
                "function": LAMMPS_FAASM_FUNC,
                "cmdline": cmdline,
                "mpi_world_size": int(nproc),
            }
            result_json = post_async_msg_and_get_result_json(msg, url)
            actual_time = get_faasm_exec_time_from_json(result_json)
            _write_csv_line(csv_name, nproc, nrep, actual_time)


@task
def native(ctx, data="compute-xl", repeats=3):
    """
    Run LAMMPS experiment on OpenMPI
    """
    pod_names, _ = get_native_mpi_pods("lammps")
    master_pod = pod_names[0]

    csv_name = "lammps_native.csv"
    _init_csv_file(csv_name)

    native_cmdline = "-in {}/{}.faasm.native".format(
        LAMMPS_DOCKER_DATA_DIR, basename(get_faasm_benchmark(data)["data"][0])
    )

    for nproc in NPROCS_EXPERIMENT:
        print(
            "Running LAMMPS on native with {} MPI processes (data: {})".format(
                nproc, data
            )
        )

        for nrep in range(repeats):
            # Prepare execution commands
            mpirun_cmd = [
                "mpirun",
                "-np {}".format(nproc),
                "-hostfile {}".format(NATIVE_HOSTFILE),
                LAMMPS_DOCKER_BINARY,
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
            exec_output = run_kubectl_cmd("lammps", " ".join(exec_cmd))
            end = time()
            print(exec_output)
            actual_time = end - start
            _write_csv_line(csv_name, nproc, nrep, actual_time)
