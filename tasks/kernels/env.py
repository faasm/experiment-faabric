from os.path import join
from tasks.util.env import PROJ_ROOT

KERNELS_NATIVE_DIR = join(PROJ_ROOT, "third-party", "kernels-native")
KERNELS_WASM_DIR = join(PROJ_ROOT, "third-party", "kernels")

KERNELS_FAASM_USER = "prk"

KERNELS_IMAGE_NAME = "experiment-kernels"
KERNELS_DOCKERFILE = join(PROJ_ROOT, "docker", "kernels.dockerfile")
