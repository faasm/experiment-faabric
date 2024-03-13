from invoke import task
from tasks.util.lulesh import (
    LULESH_DOCKER_WASM,
    LULESH_FAASM_FUNC,
    LULESH_FAASM_USER,
)
from tasks.util.upload import upload_wasm


@task()
def upload(ctx):
    """
    Upload the lulesh WASM to Granny
    """
    wasm_file_details = [
        {
            "wasm_file": LULESH_DOCKER_WASM,
            "wasm_user": LULESH_FAASM_USER,
            "wasm_function": LULESH_FAASM_FUNC,
            "copies": 1,
        },
    ]

    upload_wasm(wasm_file_details)
