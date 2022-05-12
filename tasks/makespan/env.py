from os.path import join
from tasks.util.env import PROJ_ROOT

MAKESPAN_IMAGE_NAME = "experiment-makespan"
MAKESPAN_DOCKERFILE = join(PROJ_ROOT, "docker", "makespan.dockerfile")
