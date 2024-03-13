from base64 import b64encode
from os.path import join
from tasks.util.env import EXAMPLES_DOCKER_DIR, PLOTS_ROOT, RESULTS_DIR

LULESH_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "LULESH")
LULESH_DOCKER_BINARY = join(LULESH_DOCKER_DIR, "build", "native", "lulesh2.0")
LULESH_DOCKER_WASM = join(LULESH_DOCKER_DIR, "build", "wasm", "lulesh2.0")
LULESH_FAASM_USER = "lulesh"
LULESH_FAASM_FUNC = "main"

LULESH_RESULTS_DIR = join(RESULTS_DIR, "lulesh")
LULESH_PLOTS_DIR = join(PLOTS_ROOT, "lulesh")

# Experiment parameters
LULESH_EXPECTED_NUM_VMS = 1
LULESH_EXP_NUM_THREADS = [1, 2, 3, 4, 5, 6, 7, 8]
LULESH_ITERATIONS = 50
LULESH_CUBE_SIZE = 20
LULESH_REGIONS = 11
LULESH_COST = 1
LULESH_BALANCE = 1


def get_lulesh_cmdline(
    iterations=LULESH_ITERATIONS,
    cube_size=LULESH_CUBE_SIZE,
    regions=LULESH_REGIONS,
    cost=LULESH_COST,
    balance=LULESH_BALANCE,
):
    return "-i {} -s {} -r {} -c {} -b {}".format(
        iterations, cube_size, regions, cost, balance
    )


def get_lulesh_input_data(num_threads):
    return b64encode("{}".format(num_threads).encode("utf-8")).decode("utf-8")
