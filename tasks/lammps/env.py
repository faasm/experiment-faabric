from os.path import join
from tasks.util.env import PROJ_ROOT

LAMMPS_DIR = join(PROJ_ROOT, "third-party", "lammps")

LAMMPS_IMAGE_NAME = "experiment-lammps"
LAMMPS_DOCKERFILE = join(PROJ_ROOT, "docker", "lammps.dockerfile")

DOCKER_PROJ_ROOT = "/code/experiment-mpi"
DOCKER_LAMMPS_DIR = join(DOCKER_PROJ_ROOT, "third-party", "lammps")
DOCKER_NATIVE_INSTALL_DIR = join(DOCKER_PROJ_ROOT, "build", "native-install")
DOCKER_LAMMPS_BINARY = join(DOCKER_NATIVE_INSTALL_DIR, "bin", "lmp")

LAMMPS_FAASM_USER = "lammps"
LAMMPS_FAASM_FUNC = "main"
LAMMPS_FAASM_DATA_PREFIX = "/lammps-data"

# Define the different benchmarks we run in LAMMPS

BENCHMARKS = {
    "lj": {"data": ["bench/in.lj"], "out_file": "compute"},
    "compute": {"data": ["bench/in.lj"], "out_file": "compute"},
    "compute-xl": {"data": ["bench/in.lj-xl"], "out_file": "compute"},
    "controller": {
        "data": ["examples/controller/in.controller.wall"],
        "out_file": "network",
    },
    "network": {
        "data": ["examples/controller/in.controller.wall"],
        "out_file": "network",
    },
    "eam": {"data": ["bench/in.eam", "bench/Cu_u3.eam"], "out_file": "eam"},
    "chute": {
        "data": ["bench/in.chute", "bench/data.chute"],
        "out_file": "chute",
    },
    "rhodo": {
        "data": ["bench/in.rhodo", "bench/data.rhodo"],
        "out_file": "rhodo",
    },
    "chain": {
        "data": ["bench/in.chain", "bench/data.chain"],
        "out_file": "chain",
    },
    "short": {
        "data": ["examples/controller/in.controller.wall"],
        "out_file": "short",
    },
}


def get_faasm_benchmark(bench):
    if bench not in BENCHMARKS:
        print("Unrecognized benchmark: {}".format(bench))
        print(
            "The supported LAMMPS benchmarks are: {}".format(BENCHMARKS.keys())
        )
        raise RuntimeError("Unrecognized LAMMPS benchmark")

    return BENCHMARKS[bench]
