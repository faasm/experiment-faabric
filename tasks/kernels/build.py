from invoke import task
from os.path import join
from os import makedirs
from subprocess import run
from shutil import copyfile
import requests
from sys import exit

from tasks.util import KERNELS_NATIVE_DIR, KERNELS_WASM_DIR, KERNELS_FAASM_USER

MAKE_TARGETS = [
    ("MPI1/Synch_global", "global"),
    ("MPI1/Synch_p2p", "p2p"),
    ("MPI1/Sparse", "sparse"),
    ("MPI1/Transpose", "transpose"),
    ("MPI1/Stencil", "stencil"),
    ("MPI1/DGEMM", "dgemm"),
    ("MPI1/Nstream", "nstream"),
    ("MPI1/Reduce", "reduce"),
    ("MPI1/Random", "random"),
]


@task
def native(ctx, clean=False):
    """
    Build native kernels
    """
    _do_build(KERNELS_NATIVE_DIR, clean)


@task
def wasm(ctx, clean=False):
    """
    Build kernels to wasm
    """
    _do_build(KERNELS_WASM_DIR, clean)


def _do_build(src_dir, clean):
    if clean:
        run("make clean", shell=True, cwd=src_dir)

    # Compile the kernels
    for subdir, make_target in MAKE_TARGETS:
        make_cmd = "make {}".format(make_target)
        make_dir = join(src_dir, subdir)
        res = run(make_cmd, shell=True, cwd=make_dir)

        if res.returncode != 0:
            print(
                "Making kernel in {} with target {} failed.".format(
                    subdir, make_target
                )
            )
            return


@task
def upload(ctx, host="localhost", port=8002, local=False):
    """
    Upload the LAMMPS function to Faasm
    """
    for target in [t[1] for t in MAKE_TARGETS]:
        wasm_file = join(KERNELS_WASM_DIR, "{}.wasm".format(target))

        if local:
            dest_dir = "/usr/local/faasm/wasm/{}/{}".format(
                KERNELS_FAASM_USER, target
            )
            makedirs(dest_dir, exist_ok=True)

            dest_file = join(dest_dir, "function.wasm")

            print("Copying {} to {}".format(wasm_file, dest_file))
            copyfile(wasm_file, dest_file)
        else:
            url = "http://{}:{}/f/{}/{}".format(
                host, port, KERNELS_FAASM_USER, target
            )
            print("Putting function to {}".format(url))
            response = requests.put(url, data=open(wasm_file, "rb"))
            print(
                "Response {}: {}".format(response.status_code, response.text)
            )
