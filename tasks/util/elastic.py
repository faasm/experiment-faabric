from base64 import b64encode
from os.path import join
from tasks.util.env import EXAMPLES_DOCKER_DIR, PLOTS_ROOT, RESULTS_DIR

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
OPENMP_ELASTIC_NATIVE_BINARY = join(ELASTIC_KERNELS_NATIVE_DIR, "omp_{}.wasm".format(ELASTIC_KERNEL))

# Parameters for the macrobenchmark
OPENMP_ELASTIC_NUM_LOOPS = 5


def get_elastic_input_data(num_loops=OPENMP_ELASTIC_NUM_LOOPS, native=False):
    if native:
        return "-x FAASM_BENCH_PARAMS={}".format(int(num_loops))

    return b64encode("{}".format(int(num_loops)).encode("utf-8")).decode("utf-8")
