from invoke import task
from tasks.util.elastic import (
    OPENMP_ELASTIC_FUNCTION,
    OPENMP_ELASTIC_USER,
    OPENMP_ELASTIC_WASM,
)
from tasks.util.upload import upload_wasm


@task(default=True)
def upload(ctx):
    """
    Upload the OpenMP functions to Granny
    """
    wasm_file_details = [
        {
            "wasm_file": OPENMP_ELASTIC_WASM,
            "wasm_user": OPENMP_ELASTIC_USER,
            "wasm_function": OPENMP_ELASTIC_FUNCTION,
            "copies": 1,
        }
    ]

    upload_wasm(wasm_file_details)
