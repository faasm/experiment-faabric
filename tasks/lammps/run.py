from invoke import task
from os.path import basename
from tasks.util.faasm import (
    get_faasm_invoke_host_port,
    flush_hosts,
    post_async_msg_and_get_result_json,
)
from tasks.util.openmpi import (
    NATIVE_HOSTFILE,
    get_native_mpi_pods,
    run_kubectl_cmd,
)
from tasks.lammps.env import (
    DOCKER_LAMMPS_BINARY,
    DOCKER_LAMMPS_DIR,
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_FUNC,
    get_faasm_benchmark,
)
from time import time


@task()
def granny(ctx, data="compute-xl", repeats=1, num_proc=16):
    """
    Run LAMMPS simulation on Granny
    """
    host, port = get_faasm_invoke_host_port()
    url = "http://{}:{}".format(host, port)

    # Run multiple benchmarks if desired for convenience
    data_file = basename(get_faasm_benchmark(data)["data"][0])
    print(
        "Running LAMMPS on Granny with {} MPI processes (data: {})".format(
            num_proc, data
        )
    )

    # First, flush the host state
    print("Flushing functions, state, and shared files from workers")
    flush_hosts()

    # Run LAMMPS
    cmdline = "-in faasm://lammps-data/{}".format(data_file)
    msg = {
        "user": LAMMPS_FAASM_USER,
        "function": LAMMPS_FAASM_FUNC,
        "cmdline": cmdline,
        "mpi_world_size": int(num_proc),
        "async": True,
    }
    result_json = post_async_msg_and_get_result_json(msg, url)
    print(result_json)

    # TODO: do something with results


@task
def native(ctx, data="compute-xl", repeats=1, num_procs=16):
    """
    Run LAMMPS experiment on OpenMPI
    """
    pod_names, _ = get_native_mpi_pods("lammps")
    master_pod = pod_names[0]

    native_cmdline = "-in {}/{}.faasm.native".format(
        DOCKER_LAMMPS_DIR, basename(get_faasm_benchmark(data)["data"][0])
    )
    mpirun_cmd = [
        "mpirun",
        "-np {}".format(num_procs),
        "-hostfile {}".format(NATIVE_HOSTFILE),
        DOCKER_LAMMPS_BINARY,
        native_cmdline,
    ]
    mpirun_cmd = " ".join(mpirun_cmd)

    exec_cmd = [
        "exec",
        master_pod,
        "--",
        "su mpirun -c '{}'".format(mpirun_cmd),
    ]

    start = time()
    exec_output = run_kubectl_cmd("lammps", " ".join(exec_cmd))
    end = time()
    actual_time = end - start
    print(exec_output)

    # TODO: do something with results
    print(actual_time)
