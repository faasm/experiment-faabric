from os.path import dirname, realpath, expanduser, join, exists
from shutil import rmtree
from os import makedirs
from subprocess import run

HOME_DIR = expanduser("~")
PROJ_ROOT = dirname(dirname(dirname(realpath(__file__))))
FAASM_ROOT = join(HOME_DIR, "faasm")

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
LAMMPS_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "lammps")
LAMMPS_DOCKER_BINARY = join(LAMMPS_DOCKER_DIR, "build", "native", "lmp")
LAMMPS_DOCKER_WASM = join(LAMMPS_DOCKER_DIR, "build", "wasm", "lmp")
LAMMPS_MIGRATION_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "lammps-migration")
LAMMPS_MIGRATION_DOCKER_BINARY = join(
    LAMMPS_MIGRATION_DOCKER_DIR, "build", "native", "lmp"
)
LAMMPS_MIGRATION_DOCKER_WASM = join(
    LAMMPS_MIGRATION_DOCKER_DIR, "build", "wasm", "lmp"
)
LAMMPS_FAASM_MIGRATION_FUNC = "migration"
LAMMPS_FAASM_USER = "lammps"
LAMMPS_FAASM_FUNC = "main"
LAMMPS_FAASM_DATA_PREFIX = "/lammps-data"
LULESH_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "LULESH")
LULESH_DOCKER_BINARY = join(LULESH_DOCKER_DIR, "build", "native", "lulesh2.0")
LULESH_DOCKER_WASM = join(LULESH_DOCKER_DIR, "build", "wasm", "lulesh2.0")
LULESH_FAASM_USER = "lulesh"
LULESH_FAASM_FUNC = "main"
DGEMM_DOCKER_DIR = join(EXAMPLES_DOCKER_DIR, "Kernels")
DGEMM_DOCKER_BINARY = join(DGEMM_DOCKER_DIR, "build", "native", "omp_dgemm.o")
DGEMM_DOCKER_WASM = join(DGEMM_DOCKER_DIR, "build", "wasm", "omp_dgemm.wasm")
DGEMM_FAASM_USER = "dgemm"
DGEMM_FAASM_FUNC = "main"


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
    img_tag = "faasm/{}:{}".format(img_name, get_version())
    return img_tag


def push_docker_image(img_tag):
    run("docker push {}".format(img_tag), check=True, shell=True)
