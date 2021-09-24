from invoke import task
from os.path import join
from subprocess import run

from tasks.util.env import (
    NATIVE_BUILD_DIR,
    NATIVE_INSTALL_DIR,
    clean_dir,
)
from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    generate_native_mpi_hostfile,
    get_native_mpi_pods,
    run_kubectl_cmd,
)
from tasks.lammps.env import (
    DOCKER_LAMMPS_BINARY,
    DOCKER_LAMMPS_DATA_FILE,
    LAMMPS_IMAGE_NAME,
    LAMMPS_DIR,
    PROJ_ROOT
)


@task(default=True)
def build(ctx, clean=False, verbose=False):
    """
    Build and install LAMMPS natively
    """
    # The LAMMPS CMake build instructions can be found in the following link
    # https://lammps.sandia.gov/doc/Build_cmake.html

    cmake_dir = join(LAMMPS_DIR, "cmake")

    clean_dir(NATIVE_BUILD_DIR, clean)
    clean_dir(NATIVE_INSTALL_DIR, clean)

    cmake_cmd = [
        "cmake",
        "-GNinja",
        "-DPKG_MANYBODY=yes",
        "-DCMAKE_C_COMPILER=/usr/bin/clang-10",
        "-DCMAKE_CXX_COMPILER=/usr/bin/clang++-10",
        "-DCMAKE_INSTALL_PREFIX={}".format(NATIVE_INSTALL_DIR),
        cmake_dir,
    ]

    cmake_str = " ".join(cmake_cmd)
    print(cmake_str)

    run(cmake_str, check=True, shell=True, cwd=NATIVE_BUILD_DIR)

    run("ninja", check=True, shell=True, cwd=NATIVE_BUILD_DIR)

    run("ninja install", check=True, shell=True, cwd=NATIVE_BUILD_DIR)


@task
def deploy(ctx, local=False):
    """
    Deploy the LAMMPS native MPI setup to K8s
    """
    deploy_native_mpi("lammps", LAMMPS_IMAGE_NAME)


@task
def delete(ctx):
    """
    Delete the LAMMPS native MPI setup from K8s
    """
    delete_native_mpi("lammps", LAMMPS_IMAGE_NAME)


@task
def hostfile(ctx):
    """
    Set up the LAMMPS native MPI hostfile
    """
    generate_native_mpi_hostfile("lammps")


@task
def replace_data_file(ctx, new_file_path):
    """
    Replace the existing input data file by a new one
    """
    experiment_name = "lammps"
    pod_names, pod_ips = get_native_mpi_pods(experiment_name)

    for pod_name in pod_names:
        run_kubectl_cmd(
            experiment_name,
            "cp {} {}:{}".format(
                new_file_path, pod_name, DOCKER_LAMMPS_DATA_FILE
            ),
        )


@task
def replace_binary_file(ctx):
    """
    Replace the existing binary by a new one
    """
    experiment_name = "lammps"
    pod_names, pod_ips = get_native_mpi_pods(experiment_name)

    new_bin_path = join(PROJ_ROOT, "build", "native-install", "bin", "lmp")

    for pod_name in pod_names:
        run_kubectl_cmd(
            experiment_name,
            "cp {} {}:{}".format(
                new_bin_path, pod_name, DOCKER_LAMMPS_BINARY
            ),
        )
