from invoke import task
from os.path import join
from tasks.util.env import (
    KERNELS_FAASM_FUNCS,
    KERNELS_FAASM_USER,
    KERNELS_WASM_DIR,
)
from tasks.util.upload import upload_wasm


@task()
def upload(ctx):
    """
    Upload the MPI functions to Granny
    """
    wasm_file_details = []

    for kernel in KERNELS_FAASM_FUNCS:
        wasm_file_details.append(
            {
                "wasm_file": join(
                    KERNELS_WASM_DIR, "mpi_{}.wasm".format(kernel)
                ),
                "wasm_user": KERNELS_FAASM_USER,
                "wasm_function": kernel,
                "copies": 1,
            }
        )

    upload_wasm(wasm_file_details)
