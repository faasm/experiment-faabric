from copy import copy
from os import environ, makedirs
from os.path import join, exists, dirname, realpath
from shutil import rmtree
from subprocess import run
import sys

from faasmtools.build import CMAKE_TOOLCHAIN_FILE

PROJ_ROOT = dirname(dirname(realpath(__file__)))
LAMMPS_DIR = "{}/third-party/lammps".format(PROJ_ROOT)


# The LAMMPS CMake build instructions can be found in the following link
# https://lammps.sandia.gov/doc/Build_cmake.html


def clean_dir(dir_path, clean):
    if clean and exists(dir_path):
        rmtree(dir_path)

    if not exists(dir_path):
        makedirs(dir_path)


def build_native(clean=False):
    """
    Build and install LAMMPS natively
    """
    work_dir = join(LAMMPS_DIR, "build-native")
    cmake_dir = join(LAMMPS_DIR, "cmake")
    install_dir = join(LAMMPS_DIR, "install-native")

    clean_dir(work_dir, clean)
    clean_dir(install_dir, clean)

    env_vars = copy(environ)

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


def build_faasm(clean=False):
    """
    Build and install the cross-compiled LAMMPS
    """
    work_dir = join(LAMMPS_DIR, "build")
    cmake_dir = join(LAMMPS_DIR, "cmake")
    install_dir = join(LAMMPS_DIR, "install")
    # wasm_path = join(PROJ_ROOT, "wasm", "lammps", "test", "function.wasm")

    clean_dir(work_dir, clean)
    clean_dir(install_dir, clean)

    env_vars = copy(environ)

    cmake_cmd = [
        "cmake",
        "-GNinja",
        "-DLAMMPS_FAASM=ON",
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
# 
# 
# def copy_wasm(clean=False):
#     """
#     Manually copy the LAMMPS binary to the Faasm func dir
#     """
#     install_dir = join(LAMMPS_DIR, "install", "bin")
#     faasm_func_dir = "/usr/local/code/faasm/wasm/lammps/main"
#     cmd = [
#         "cp",
#         "{}/lmp".format(install_dir),
#         "{}/function.wasm".format(faasm_func_dir),
#     ]
# 
#     cmd = " ".join(cmd)
#     print(cmd)
# 
#     res = run(cmd, shell=True)
#     if res.returncode != 0:
#         raise RuntimeError("Copying wasm file failed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: ./build/lammps.py native|faasm [--clean]")
        sys.exit(1)
    elif sys.argv[1] not in ["native", "faasm"]:
        print("usage: ./build/lammps.py native|faasm [--clean]")
        sys.exit(1)
    else:
        clean = False
        if len(sys.argv) > 2 and sys.argv[2] == "--clean":
            clean = True
        if sys.argv[1] == "native":
            build_native(clean)
        else:
            build_faasm(clean)
