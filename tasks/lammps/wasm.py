from invoke import task
import requests
from shutil import copyfile
from os.path import join
from os import makedirs
from subprocess import run

from tasks.util import (
    WASM_BUILD_DIR,
    LAMMPS_DIR,
    WASM_INSTALL_DIR,
    clean_dir,
    FAASM_USER,
    FAASM_FUNC,
)

CMAKE_TOOLCHAIN_FILE = "/usr/local/faasm/toolchain/tools/WasiToolchain.cmake"


@task(default=True)
def build(ctx, clean=False, verbose=False):
    """
    Build LAMMPS to wasm
    """
    cmake_dir = join(LAMMPS_DIR, "cmake")

    clean_dir(WASM_BUILD_DIR, clean)
    clean_dir(WASM_INSTALL_DIR, clean)

    cmake_cmd = [
        "cmake",
        "-GNinja",
        "-DLAMMPS_FAASM=ON",
        "-DCMAKE_TOOLCHAIN_FILE={}".format(CMAKE_TOOLCHAIN_FILE),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_INSTALL_PREFIX={}".format(WASM_INSTALL_DIR),
        cmake_dir,
    ]

    cmake_str = " ".join(cmake_cmd)
    print(cmake_str)

    res = run(cmake_str, shell=True, cwd=WASM_BUILD_DIR)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS CMake config failed")

    res = run("ninja", shell=True, cwd=WASM_BUILD_DIR)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS build failed")

    res = run("ninja install", shell=True, cwd=WASM_BUILD_DIR)
    if res.returncode != 0:
        raise RuntimeError("LAMMPS install failed")


@task
def upload(ctx, host="localhost", port=8002, local=False):
    """
    Upload the LAMMPS function to Faasm
    """
    wasm_file = join(WASM_INSTALL_DIR, "bin", "lmp")

    if local:
        dest_dir = "/usr/local/faasm/wasm/{}/{}".format(FAASM_USER, FAASM_FUNC)
        makedirs(dest_dir, exist_ok=True)

        dest_file = join(dest_dir, "function.wasm")

        print("Copying {} to {}".format(wasm_file, dest_file))
        copyfile(wasm_file, dest_file)
    else:
        url = "http://{}:{}/f/{}/{}".format(host, port, FAASM_USER, FAASM_FUNC)
        print("Putting function to {}".format(url))
        response = requests.put(url, data=open(wasm_file, "rb"))
        print("Response {}: {}".format(response.status_code, response.text))
