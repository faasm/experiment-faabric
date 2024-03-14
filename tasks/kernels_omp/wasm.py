from invoke import task
from os.path import join
from tasks.util.kernels import (
    KERNELS_WASM_DIR,
    OPENMP_KERNELS,
    OPENMP_KERNELS_FAASM_USER,
)
from tasks.util.upload import upload_wasm


@task(default=True)
def upload(ctx):
    """
    Upload the OpenMP functions to Granny
    """
    wasm_file_details = []
    for kernel in OPENMP_KERNELS:
        wasm_file_details.append(
            {
                "wasm_file": join(
                    KERNELS_WASM_DIR, "omp_{}.wasm".format(kernel)
                ),
                "wasm_user": OPENMP_KERNELS_FAASM_USER,
                "wasm_function": kernel,
                "copies": 1,
            }
        )

    upload_wasm(wasm_file_details)
