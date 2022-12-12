from invoke import task
from tasks.makespan.env import (
    DGEMM_DOCKER_WASM,
    DGEMM_FAASM_USER,
    DGEMM_FAASM_FUNC,
    LULESH_DOCKER_WASM,
    LULESH_FAASM_USER,
    LULESH_FAASM_FUNC,
)
from tasks.util.upload import upload_wasm


@task(default=True)
def upload(ctx):
    """
    Upload the OpenMP functions to Granny
    """
    wasm_file_details = [
        {
            "wasm_file": LULESH_DOCKER_WASM,
            "wasm_user": LULESH_FAASM_USER,
            "wasm_function": LULESH_FAASM_FUNC,
            "copies": 1,
        },
        {
            "wasm_file": DGEMM_DOCKER_WASM,
            "wasm_user": DGEMM_FAASM_USER,
            "wasm_function": DGEMM_FAASM_FUNC,
            "copies": 1,
        },
    ]

    upload_wasm(wasm_file_details)
