from os.path import join
from tasks.util.env import EXAMPLES_BASE_DIR, EXAMPLES_DOCKER_DIR

POLYBENCH_USER = "polybench"
POLYBENCH_DOCKER_DIR = join(EXAMPLES_BASE_DIR, POLYBENCH_USER)
POLYBENCH_NATIVE_DOCKER_BUILD_DIR = join(
    EXAMPLES_DOCKER_DIR, "polybench", "build", "native"
)

# This list of functions can be obtained by going to the examples directory,
# and listing the files in `./dev/faasm-local/wasm/polybench`
POLYBENCH_FUNCS = [
    "poly_2mm",
    "poly_3mm",
    "poly_adi",
    "poly_atax",
    "poly_bicg",
    "poly_cholesky",
    "poly_correlation",
    "poly_covariance",
    "poly_deriche",
    "poly_doitgen",
    "poly_durbin",
    "poly_fdtd-2d",
    "poly_floyd-warshall",
    "poly_gramschmidt",
    "poly_heat-3d",
    "poly_jacobi-1d",
    "poly_jacobi-2d",
    "poly_lu",
    "poly_ludcmp",
    "poly_mvt",
    "poly_nussinov",
    "poly_seidel-2d",
    "poly_trisolv",
]
