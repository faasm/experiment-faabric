from faasmctl.util.planner import get_available_hosts, reset as reset_planner
from invoke import task
from os import makedirs
from os.path import basename, join
from random import sample
from subprocess import run
from tasks.util.compose import NUM_CORES_PER_CTR, get_compose_ctrs
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from tasks.util.lammps import (
    LAMMPS_FAASM_USER,
    LAMMPS_MIGRATION_NET_DOCKER_BINARY,
    LAMMPS_MIGRATION_NET_DOCKER_DIR,
    LAMMPS_FAASM_MIGRATION_NET_FUNC,
    get_lammps_migration_params,
)
from tasks.util.openmpi import OPENMPI_RESULTS_DIR
from tasks.util.planner import get_xvm_links_from_part
from time import sleep, time

# Parameters tuning the experiment runs
NPROCS_EXPERIMENT = list(range(2, 17))
PARTITIONS_CSV = join(OPENMPI_RESULTS_DIR, "partitions.csv")


def init_csv_file(csv_name):
    makedirs(OPENMPI_RESULTS_DIR, exist_ok=True)
    result_file = join(OPENMPI_RESULTS_DIR, csv_name)
    with open(result_file, "w") as out_file:
        out_file.write("Part,CrossVmLinks,Time\n")

    return result_file


def write_csv_line(csv_name, part, xvm_links, actual_time):
    result_file = join(OPENMPI_RESULTS_DIR, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{:.2f}\n".format(part, xvm_links, actual_time))


def get_native_host_list_from_part(part):
    """
    A partition is a comma separated list of processes-to-container allocation.
    Additionally, different partitions can be concatenated using a colon.
    From the partition, we can work out the MPI world size.
    """
    ctr_names, ctr_ips = get_compose_ctrs()
    host_list = []

    for i, num in enumerate(part):
        assert i < len(ctr_ips), "Ran out of container IPs!"

        host_list += [ctr_ips[i]] * int(num)

    return host_list


def get_wasm_host_list_from_part(part):
    """
    Generate a host list given an array of the number of MPI processes that
    need to go in each host.
    """
    avail_hosts = get_available_hosts()
    host_list = []

    # Sanity check the host list. First, for this experiment we should only
    # have two regsitered workers
    assert len(avail_hosts.hosts) >= len(
        part
    ), "Not enough available hosts (have: {} - need: {})".format(
        len(avail_hosts.hosts), len(part)
    )
    for ind, num_in_host in enumerate(part):
        host = avail_hosts.hosts[ind]
        # Second, each host should have no other running messages
        # assert host.usedSlots == 0, "Not enough free slots on host!"
        # Third, each host should have enough slots to run the requested number
        # of messages
        assert host.slots >= num_in_host, "Not enough slots on host!"

        host_list = host_list + int(num_in_host) * [host.ip]

    return host_list


def get_nproc_from_part(part):
    nproc = 0
    for p in part:
        assert p <= NUM_CORES_PER_CTR, "Too many procs per container!"
        nproc += p

    return nproc


def partition(number):
    answer = set()
    answer.add((number,))
    for x in range(1, number):
        for y in partition(number - x):
            answer.add(tuple(sorted((x,) + y)))
    return answer


@task
def generate_partitions(ctx, max_num_partitions=5):
    all_parts = []
    ctr_names, ctr_ips = get_compose_ctrs()
    num_vms = len(ctr_names)

    for n_proc in [2, 4, 8]:
        partitions = partition(n_proc)

        # Prune the number of partitions we will explore to a hard cap
        partitions = [
            part for part in partitions if max(part) <= NUM_CORES_PER_CTR
        ]
        partitions = [
            part for part in partitions if len(part) <= num_vms
        ]
        if len(partitions) > max_num_partitions:
            links = [
                (ind, get_xvm_links_from_part(p))
                for ind, p in enumerate(partitions)
            ]
            links = sorted(links, key=lambda x: x[1])
            sampled_links = (
                [links[0]]
                + sample(links[1:-1], max_num_partitions - 2)
                + [links[-1]]
            )
            pruned_partitions = [partitions[link[0]] for link in sampled_links]
        else:
            pruned_partitions = partitions

        all_parts += pruned_partitions

    makedirs(OPENMPI_RESULTS_DIR, exist_ok=True)
    with open(PARTITIONS_CSV, "w") as fh:
        for part in all_parts:
            fh.write("{}\n".format(",".join([str(p) for p in part])))

    return all_parts


def load_partitions_from_file():
    parts = []
    with open(PARTITIONS_CSV, "r") as fh:
        for line in fh:
            parts.append([int(p) for p in line.strip().split(",")])

    return parts


@task()
def native(ctx):
    """
    Run an experiment with OpenMPI

    TODO:
    - read/write to file
    - integrate with oracle
    """
    do_run(native=True)


@task
def wasm(ctx):
    avail_hosts = get_available_hosts()
    reset_planner(len(avail_hosts.hosts))

    do_run(native=False)


EXP_CONFIG = {
    # very sensitive to locality, maybe a bit fake?
    "conf1": {
        "data_file": "bench/in.lj",
        "lammps_params": {
            "num_loops": 3,
            "num_net_loops": 1e6,
            "chunk_size": 1e1,
        }
    },
    "conf2": {
        "data_file": "examples/controller/in.controller.wall",
        "lammps_params": {
            "num_loops": 1,
            "num_net_loops": 0,
            "chunk_size": 1e1,
        }
    },
}


def do_run(native):
    partitions = load_partitions_from_file()
    csv_name = "openmpi_oracle_{}.csv".format("native" if native else "granny")
    init_csv_file(csv_name)

    # A partition is a comma separated list of procs-to-host mapping
    conf = EXP_CONFIG["conf2"]
    for part in partitions:
        print(
            "Running LAMMPS ({}) with {} MPI procs (data file: {}, params: {}, part: {}, xvm: {})".format(
                "native" if native else "wasm",
                get_nproc_from_part(part),
                conf["data_file"],
                ",".join([str(itm) for itm in conf["lammps_params"].values()]),
                part,
                get_xvm_links_from_part(part),
            )
        )

        if native:
            actual_time = run_native(part, conf)
        else:
            actual_time = run_wasm(part, conf)
        write_csv_line(csv_name, part, get_xvm_links_from_part(part), actual_time)


def run_wasm(part, config):
    user = LAMMPS_FAASM_USER
    func = LAMMPS_FAASM_MIGRATION_NET_FUNC
    file_name = basename(config["data_file"])
    cmdline = "-in faasm://lammps-data/{}".format(file_name)

    msg = {
        "user": user,
        "function": func,
        "mpi": True,
        "mpi_world_size": get_nproc_from_part(part),
        "cmdline": cmdline,
        # We never want to migrate in this experiment, as we are only comparing
        # our slowdown wrt OpenMPI for a given partition
        "input_data": get_lammps_migration_params(
            check_every=config["lammps_params"]["num_loops"],
            num_loops=config["lammps_params"]["num_loops"],
            num_net_loops=config["lammps_params"]["num_net_loops"],
            chunk_size=config["lammps_params"]["chunk_size"],
        ),
    }

    result_json = post_async_msg_and_get_result_json(
        msg, host_list=get_wasm_host_list_from_part(part)
    )
    actual_time = get_faasm_exec_time_from_json(result_json)
    print("Actual time: {}".format(actual_time))
    sleep(2)

    return actual_time


def run_native(part, config):
    ctr_names, ctr_ips = get_compose_ctrs()
    main_ctr = ctr_names[0]

    native_cmdline = "-in {}/{}.faasm.native".format(
        LAMMPS_MIGRATION_NET_DOCKER_DIR,
        config["data_file"],
    )

    # Prepare execution commands
    mpirun_cmd = [
        "mpirun",
        get_lammps_migration_params(
            native=True,
            num_loops=config["lammps_params"]["num_loops"],
            num_net_loops=config["lammps_params"]["num_net_loops"],
            chunk_size=config["lammps_params"]["chunk_size"],
        ),
        "-np {}".format(get_nproc_from_part(part)),
        "-host {}".format(",".join(get_native_host_list_from_part(part))),
        LAMMPS_MIGRATION_NET_DOCKER_BINARY,
        native_cmdline,
    ]
    mpirun_cmd = " ".join(mpirun_cmd)
    docker_cmd = [
        "docker",
        "exec",
        main_ctr,
        "bash -c \"su mpirun -c '{}'\"".format(mpirun_cmd),
    ]
    docker_cmd = " ".join(docker_cmd)

    # Run command
    start = time()
    run(docker_cmd, shell=True, check=True, capture_output=True)
    end = time()
    actual_time = round(end - start, 2)
    print("Actual time: {}".format(actual_time))
    sleep(2)

    return actual_time
