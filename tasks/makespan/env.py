from os.path import join
from tasks.util.env import PROJ_ROOT

MAKESPAN_DIR = join(PROJ_ROOT, "tasks", "makespan")
MAKESPAN_IMAGE_NAME = "experiment-makespan"
MAKESPAN_DOCKERFILE = join(PROJ_ROOT, "docker", "makespan.dockerfile")

MIGRATE_NATIVE_BINARY = "mpi_migrate"
