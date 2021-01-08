from os.path import join
from subprocess import run
from copy import copy
import os

from faasmtools.build import CMAKE_TOOLCHAIN_FILE
from tasks.util.file import clean_dir
from invoke import task

from tasks.util.env import EXPERIMENT_ROOT

LAMMPS_DIR = join(EXPERIMENT_ROOT, "lammps")


# The LAMMPS CMake build instructions can be found in the following link
# https://lammps.sandia.gov/doc/Build_cmake.html


@task(default=True)
def build(ctx, clean=False):
    """
    Build and install the cross-compiled LAMMPS
    """
    work_dir = join(LAMMPS_DIR, "build")
    cmake_dir = join(LAMMPS_DIR, "cmake")
    install_dir = join(LAMMPS_DIR, "install")
    # wasm_path = join(PROJ_ROOT, "wasm", "lammps", "test", "function.wasm")

    clean_dir(work_dir, clean)
    clean_dir(install_dir, clean)

    env_vars = copy(os.environ)

    cmake_cmd = [
        "cmake",
        "-GNinja",
        "-DCMAKE_TOOLCHAIN_FILE={}".format(CMAKE_TOOLCHAIN_FILE),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_INSTALL_PREFIX={}".format(install_dir),
        cmake_dir,
    ]

    cmake_str = " ".join(cmake_cmd)
    print(cmake_str)

    res = run(cmake_str, shell=True, cwd=work_dir, env=env_vars)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS CMake config failed")

    res = run("ninja", shell=True, cwd=work_dir)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS build failed")

    res = run("ninja install", shell=True, cwd=work_dir)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS install failed")


@task
def native(ctx, clean=False):
    """
    Build and install LAMMPS natively
    """
    work_dir = join(LAMMPS_DIR, "build-native")
    cmake_dir = join(LAMMPS_DIR, "cmake")
    install_dir = join(LAMMPS_DIR, "install-native")

    clean_dir(work_dir, clean)
    clean_dir(install_dir, clean)

    env_vars = copy(os.environ)

    cmake_cmd = [
        "cmake",
        "-GNinja",
        "-DCMAKE_C_COMPILER=/usr/bin/clang-10",
        "-DCMAKE_CXX_COMPILER=/usr/bin/clang++-10",
        "-DCMAKE_INSTALL_PREFIX={}".format(install_dir),
        cmake_dir,
    ]

    cmake_str = " ".join(cmake_cmd)
    print(cmake_str)

    res = run(cmake_str, shell=True, cwd=work_dir, env=env_vars)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS native CMake config failed")

    res = run("ninja", shell=True, cwd=work_dir)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS native build failed")

    res = run("ninja install", shell=True, cwd=work_dir)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS install failed")


@task
def copy_wasm(ctx, clean=False):
    """
    Manually copy the LAMMPS binary to the Faasm func dir
    """
    install_dir = join(LAMMPS_DIR, "install", "bin")
    faasm_func_dir = "/usr/local/code/faasm/wasm/lammps/main"
    cmd = [
        "cp",
        "{}/lmp".format(install_dir),
        "{}/function.wasm".format(faasm_func_dir),
    ]

    cmd = " ".join(cmd)
    print(cmd)

    res = run(cmd, shell=True)
    if res.returncode != 0:
        raise RuntimeError("Copying wasm file failed")
