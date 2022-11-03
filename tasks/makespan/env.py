from os.path import join
from tasks.util.env import PROJ_ROOT
from tasks.lammps.env import DOCKER_NATIVE_INSTALL_DIR

MAKESPAN_DIR = join(PROJ_ROOT, "tasks", "makespan")
MAKESPAN_NATIVE_COMPOSE_NAME = "makespan-native"
MAKESPAN_NATIVE_DIR = join(MAKESPAN_DIR, "native")
MAKESPAN_WASM_DIR = join(MAKESPAN_DIR, "wasm")
MAKESPAN_IMAGE_NAME = "experiment-makespan"
MAKESPAN_DOCKERFILE = join(PROJ_ROOT, "docker", "makespan.dockerfile")

MIGRATE_NATIVE_BINARY = "mpi_migrate"
MIGRATE_FAASM_USER = "mpi"
MIGRATE_FAASM_FUNC = "migrate"
DOCKER_MIGRATE_BINARY = join(DOCKER_NATIVE_INSTALL_DIR, MIGRATE_NATIVE_BINARY)
