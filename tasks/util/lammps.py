from base64 import b64encode
from os.path import join
from tasks.util.env import EXAMPLES_DOCKER_DIR, PLOTS_ROOT, RESULTS_DIR
from tasks.util.upload import upload_files

LAMMPS_PLOTS_DIR = join(PLOTS_ROOT, "lammps")
LAMMPS_RESULTS_DIR = join(RESULTS_DIR, "lammps")

LAMMPS_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "lammps")
LAMMPS_MIGRATION_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "lammps-migration")
LAMMPS_MIGRATION_NET_DOCKER_DIR = join(
    EXAMPLES_DOCKER_DIR, "lammps-migration-net"
)
LAMMPS_DOCKER_DATA_DIR = join(LAMMPS_DOCKER_DIR, "bench")
LAMMPS_FAASM_DATA_PREFIX = "/lammps-data"

# Native binaries
LAMMPS_DOCKER_BINARY = join(LAMMPS_DOCKER_DIR, "build", "native", "lmp")
LAMMPS_MIGRATION_DOCKER_BINARY = join(
    LAMMPS_MIGRATION_DOCKER_DIR, "build", "native", "lmp"
)
LAMMPS_MIGRATION_NET_DOCKER_BINARY = join(
    LAMMPS_MIGRATION_NET_DOCKER_DIR, "build", "native", "lmp"
)

# WASM binaries
LAMMPS_DOCKER_WASM = join(LAMMPS_DOCKER_DIR, "build", "wasm", "lmp")
LAMMPS_MIGRATION_DOCKER_WASM = join(
    LAMMPS_MIGRATION_NET_DOCKER_DIR, "build", "wasm", "lmp"
)
LAMMPS_MIGRATION_NET_DOCKER_WASM = join(
    LAMMPS_MIGRATION_NET_DOCKER_DIR, "build", "wasm", "lmp"
)

# Faasm user/function pairs
LAMMPS_FAASM_USER = "lammps"
LAMMPS_FAASM_FUNC = "main"
LAMMPS_FAASM_MIGRATION_FUNC = "migration"
LAMMPS_FAASM_MIGRATION_NET_FUNC = "migration-net"

# Intra-experiment configuration shared among experiments
# LAMMPS_SIM_WORKLOAD = "compute-xl"
LAMMPS_SIM_WORKLOAD = "compute"
# LAMMPS_SIM_NUM_ITERATIONS = 3
LAMMPS_SIM_NUM_ITERATIONS = 10
LAMMPS_SIM_CHECK_AT = LAMMPS_SIM_NUM_ITERATIONS
LAMMPS_SIM_NUM_NET_LOOPS = 1e4
LAMMPS_SIM_CHUNK_SIZE = 2e4

LAMMPS_SIM_WORKLOAD_CONFIGS = {
    "compute": {
        "data_file": "compute",
        "num_iterations": 10,
        "num_net_loops": 0,
        "chunk_size": 0,
    },
    "network": {
        "data_file": "compute",
        "num_iterations": 10,
        "num_net_loops": LAMMPS_SIM_NUM_NET_LOOPS,
        "chunk_size": LAMMPS_SIM_CHUNK_SIZE,
    },
    "very-network": {
        "data_file": "compute",
        "num_iterations": 10,
        "num_net_loops": 1e6,
        "chunk_size": 10,
    },
    "og-network": {
        "data_file": "network",
        "num_iterations": 10,
        "num_net_loops": 0,
        "chunk_size": 0,
    },
}

# Different supported LAMMPS benchmarks
# 18/04/2024 - Seems that we may want to run `compute` with a high number of
# iterations
BENCHMARKS = {
    "lj": {"data": ["bench/in.lj"], "out_file": "compute"},
    "compute": {"data": ["bench/in.lj"], "out_file": "compute"},
    "compute-xl": {"data": ["bench/in.lj-xl"], "out_file": "compute"},
    "compute-xxl": {"data": ["bench/in.lj-xxl"], "out_file": "compute"},
    "controller": {
        "data": ["examples/controller/in.controller.wall"],
        "out_file": "network",
    },
    "network": {
        "data": ["examples/controller/in.controller.wall"],
        "out_file": "network",
    },
    "eam": {"data": ["bench/in.eam", "bench/Cu_u3.eam"], "out_file": "eam"},
    "chute": {
        "data": ["bench/in.chute", "bench/data.chute"],
        "out_file": "chute",
    },
    "rhodo": {
        "data": ["bench/in.rhodo", "bench/data.rhodo"],
        "out_file": "rhodo",
    },
    "chain": {
        "data": ["bench/in.chain", "bench/data.chain"],
        "out_file": "chain",
    },
    "short": {
        "data": ["examples/controller/in.controller.wall"],
        "out_file": "short",
    },
}


def get_lammps_data_file(workload):
    return BENCHMARKS[workload]


def get_lammps_workload(workload):
    if workload not in LAMMPS_SIM_WORKLOAD_CONFIGS:
        print("Unrecognized workload: {}".format(workload))
        print(
            "The supported LAMMPS workloads are: {}".format(LAMMPS_SIM_WORKLOAD_CONFIGS.keys())
        )
        raise RuntimeError("Unrecognized LAMMPS workload")

    return LAMMPS_SIM_WORKLOAD_CONFIGS[workload]


def get_lammps_migration_params(
    check_every=LAMMPS_SIM_CHECK_AT,
    num_loops=LAMMPS_SIM_NUM_ITERATIONS,
    # num_net_loops=LAMMPS_SIM_NUM_NET_LOOPS,
    num_net_loops=0,
    chunk_size=LAMMPS_SIM_CHUNK_SIZE,
    native=False,
):
    if native:
        return "-x FAASM_BENCH_PARAMS={}:{}:{}".format(
            int(num_loops), int(num_net_loops), int(chunk_size)
        )

    # We add an extra whitespace because there seems to be a strange bug when
    # encoding/decoding input data with a 4-digit chunk size. Adding the
    # whitespace works-around the issue
    return b64encode(
        "{} {} {} {} ".format(
            int(check_every),
            int(num_loops),
            int(num_net_loops),
            int(chunk_size),
        ).encode("utf-8")
    ).decode("utf-8")


def lammps_data_upload(ctx, bench):
    """
    Upload LAMMPS benchmark data to Faasm
    """
    file_details = []

    for b in bench:
        _bench = get_lammps_data_file(b)

        # Upload all data corresponding to the benchmark
        for data in _bench["data"]:
            file_name = data.split("/")[-1]
            host_path = join(LAMMPS_DOCKER_DIR, data + ".faasm")
            faasm_path = join(LAMMPS_FAASM_DATA_PREFIX, file_name)

            file_details.append(
                {"host_path": host_path, "faasm_path": faasm_path}
            )

    upload_files(file_details)
