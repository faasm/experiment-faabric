from os.path import dirname, realpath, expanduser, join, exists
from shutil import rmtree
from os import makedirs
from subprocess import run

HOME_DIR = expanduser("~")
PROJ_ROOT = dirname(dirname(dirname(realpath(__file__))))
FAASM_ROOT = join(HOME_DIR, "faasm")

ACR_NAME = "faasm.azurecr.io"
FAABRIC_EXP_IMAGE_NAME = "faabric-experiments"

NATIVE_BUILD_DIR = join(PROJ_ROOT, "build", "native")
NATIVE_INSTALL_DIR = join(PROJ_ROOT, "build", "native-install")

WASM_BUILD_DIR = join(PROJ_ROOT, "build", "wasm")
WASM_INSTALL_DIR = join(PROJ_ROOT, "build", "wasm-install")

RESULTS_DIR = join(PROJ_ROOT, "results")

PLOTS_ROOT = join(PROJ_ROOT, "plots")
PLOTS_FORMAT = "pdf"
MPL_STYLE_FILE = join(PROJ_ROOT, "faasm.mplstyle")

# ------------------------------------------
# Constants related to function upload and exectuion
# ------------------------------------------

EXAMPLES_BASE_DIR = join("/code", "faasm-examples")
EXAMPLES_DOCKER_DIR = join(EXAMPLES_BASE_DIR, "examples")

# --- LULESH ---

LULESH_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "LULESH")
LULESH_DOCKER_BINARY = join(LULESH_DOCKER_DIR, "build", "native", "lulesh2.0")
LULESH_DOCKER_WASM = join(LULESH_DOCKER_DIR, "build", "wasm", "lulesh2.0")
LULESH_FAASM_USER = "lulesh"
LULESH_FAASM_FUNC = "main"

# --- DGEMM (OpenMP Kernel) ---

DGEMM_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "Kernels")
DGEMM_DOCKER_BINARY = join(DGEMM_DOCKER_DIR, "build", "native", "omp_dgemm.o")
DGEMM_DOCKER_WASM = join(DGEMM_DOCKER_DIR, "build", "wasm", "omp_dgemm.wasm")
DGEMM_FAASM_USER = "dgemm"
DGEMM_FAASM_FUNC = "main"

# --- OpenMP Kernels ---

OPENMP_KERNELS_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "Kernels")
OPENMP_KERNELS = ["global", "p2p", "sparse", "nstream", "reduce", "dgemm"]
OPENMP_KERNELS_FAASM_USER = "kernels-omp"

# --- MPI Migration Microbenchmark

MPI_MIGRATE_WASM_BINARY = join(EXAMPLES_BASE_DIR, "mpi_migrate.wasm")
MPI_MIGRATE_FAASM_USER = "mpi"
MPI_MIGRATE_FAASM_FUNC = "migrate"


def get_version():
    ver_file = join(PROJ_ROOT, "VERSION")

    with open(ver_file, "r") as fh:
        version = fh.read()
        version = version.strip()

    return version


def clean_dir(dir_path, clean):
    if clean and exists(dir_path):
        rmtree(dir_path)

    if not exists(dir_path):
        makedirs(dir_path)


def get_docker_tag(img_name):
    img_tag = "{}/{}:{}".format(ACR_NAME, img_name, get_version())
    return img_tag


def push_docker_image(img_tag):
    run("docker push {}".format(img_tag), check=True, shell=True)
