from invoke import task
from os.path import join
from tasks.util.upload import upload_wasm
from tasks.kernels.env import (
    KERNELS_WASM_DIR,
    KERNELS_FAASM_USER,
)

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
def upload(ctx):
    """
    Upload the MPI Kernes to Faasm
    """
    wasm_file_details = []
    for target in [t[1] for t in MAKE_TARGETS]:
        wasm_file = join(KERNELS_WASM_DIR, "wasm", "{}.wasm".format(target))
        wasm_file_details.append(
            {
                "wasm_file": wasm_file,
                "wasm_user": KERNELS_FAASM_USER,
                "wasm_function": target,
                "copies": 1,
            }
        )

    upload_wasm(wasm_file_details)
