from invoke import task
from os.path import join
from subprocess import run
from sys import exit

from tasks.util import PROJ_ROOT, WASM_DIR, FAASM_DIR

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


@task(default=True)
def build(ctx, mode, clean=False):
    """
    Compile and install the ParRes kernels
    """
    if mode == "native":
        src_dir = NATIVE_CODE_DIR
    elif mode == "wasm":
        src_dir = WASM_CODE_DIR
    else:
        print("ERROR: unknown mode `{}`".format(mode))
        exit(1)

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
def upload_wasm(ctx):
    """
    Upload wasm code in place
    """
    for target in [t[1] for t in MAKE_TARGETS]:
        wasm_src = join(WASM_DIR, "{}.wasm".format(target))
        cmd = "inv -r faasmcli/faasmcli upload prk {} {}".format(
            target, wasm_src
        )
        print(cmd)
        run(cmd, shell=True, check=True, cwd=FAASM_DIR)
