from os.path import join
from tasks.util.env import PROJ_ROOT

LAMMPS_DIR = join(PROJ_ROOT, "third-party", "lammps")
LAMMPS_DATA_FILE = join(
    LAMMPS_DIR, "examples", "controller", "in.controller.wall"
)

LAMMPS_IMAGE_NAME = "experiment-lammps"
LAMMPS_DOCKERFILE = join(PROJ_ROOT, "docker", "lammps.dockerfile")

DOCKER_PROJ_ROOT = "/code/experiment-mpi"
DOCKER_LAMMPS_DIR = join(DOCKER_PROJ_ROOT, "third-party", "lammps")
DOCKER_NATIVE_INSTALL_DIR = join(DOCKER_PROJ_ROOT, "build", "native-install")
DOCKER_LAMMPS_BINARY = join(DOCKER_NATIVE_INSTALL_DIR, "bin", "lmp")
DOCKER_LAMMPS_DATA_FILE = join(
    DOCKER_LAMMPS_DIR, "examples", "controller", "in.controller.wall"
)

LAMMPS_FAASM_USER = "lammps"
LAMMPS_FAASM_FUNC = "main"
