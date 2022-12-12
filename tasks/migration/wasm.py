from invoke import task
from tasks.util.env import (
    MPI_MIGRATE_WASM_BINARY,
    MPI_MIGRATE_FAASM_USER,
    MPI_MIGRATE_FAASM_FUNC,
)
from tasks.util.upload import upload_wasm


@task()
def upload(ctx):
    """
    Upload the migration microbenchmark function to Granny
    """
    wasm_file_details = [
        {
            "wasm_file": MPI_MIGRATE_WASM_BINARY,
            "wasm_user": MPI_MIGRATE_FAASM_USER,
            "wasm_function": MPI_MIGRATE_FAASM_FUNC,
            "copies": 1,
        },
    ]

    upload_wasm(wasm_file_details)
