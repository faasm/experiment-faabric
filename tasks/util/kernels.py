from os.path import join
from tasks.util.env import EXAMPLES_DOCKER_DIR, PLOTS_ROOT, RESULTS_DIR

# -------------------
# All Kernels
# -------------------

KERNELS_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "Kernels")
KERNELS_WASM_DIR = join(KERNELS_DOCKER_DIR, "build", "wasm")
KERNELS_NATIVE_DIR = join(KERNELS_DOCKER_DIR, "build", "native")

# -------------------
# MPI Kernels
# -------------------

MPI_KERNELS_FAASM_USER = "kernels-mpi"
MPI_KERNELS_FAASM_FUNCS = [
    "p2p",
    "sparse",
    "transpose",
    "reduce",
    # nstream: some spurious errors
    "nstream",
    "stencil",
]

# Experiment parameters
MPI_KERNELS_EXPERIMENT_NPROCS = [2, 4, 6, 8, 10, 12, 14, 16]

MPI_KERNELS_PLOTS_DIR = join(PLOTS_ROOT, "kernels-mpi")
MPI_KERNELS_RESULTS_DIR = join(RESULTS_DIR, "kernels-mpi")

# -------------------
# OpenMP Kernels
# -------------------

OPENMP_KERNELS_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "Kernels")
OPENMP_KERNELS = ["global", "p2p", "sparse", "nstream", "reduce", "dgemm"]
OPENMP_KERNELS_FAASM_USER = "kernels-omp"

OPENMP_KERNELS_PLOTS_DIR = join(PLOTS_ROOT, "kernels-omp")
OPENMP_KERNELS_RESULTS_DIR = join(RESULTS_DIR, "kernels-omp")


def get_openmp_kernel_cmdline(kernel, num_threads):
    kernels_cmdline = {
        # dgemm: iterations, order, tile size (20 iterations fine, 100 long)
        "dgemm": "100 2048 32",
        # global: iterations, scramble string length
        # string length must be multiple of num_threads
        "global": "10000 {}".format(1 * 2 * 3 * 4 * 5 * 6 * 7 * 8 * 2),
        # nstream: iterations, vector length, offset
        # nstream vector length gets OOM somewhere over 50000000 in wasm
        "nstream": "1000 50000000 32",
        # p2p: iterations, 1st array dimension, 2nd array dimension
        # p2p arrays get OOM somewhere over 10000 x 10000 in wasm
        "p2p": "200 10000 10000",
        # pic: simulation steps, grid size, n particles, k, m
        "pic": [10, 1000, 5000000, 1, 0, "LINEAR", 1.0, 3.0],
        # reduce: iterations, vector length
        "reduce": "200 10000000",
        # sparse: iterations, 2log grid size, radius
        "sparse": "1000 10 12",
        # stencil: iterations, array dimension
        "stencil": "10 10000",
        # transpose: iterations, matrix order, tile size
        "transpose": "10 8000 32",
    }

    return "{} {}".format(num_threads, kernels_cmdline[kernel])
