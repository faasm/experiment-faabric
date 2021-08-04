from invoke import task
from os.path import join
from tasks.util import (
    NATIVE_BUILD_DIR,
    LAMMPS_DIR,
    NATIVE_INSTALL_DIR,
    clean_dir,
)
from subprocess import run

# The LAMMPS CMake build instructions can be found in the following link
# https://lammps.sandia.gov/doc/Build_cmake.html


@task(default=True)
def build(ctx, clean=False, verbose=False):
    """
    Build and install LAMMPS natively
    """
    cmake_dir = join(LAMMPS_DIR, "cmake")

    clean_dir(NATIVE_BUILD_DIR, clean)
    clean_dir(NATIVE_INSTALL_DIR, clean)

    cmake_cmd = [
        "cmake",
        "-GNinja",
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
