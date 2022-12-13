from invoke import task
from os.path import join
from tasks.lammps.data import upload as lammps_data_upload
from tasks.util.env import (
    LAMMPS_MIGRATION_DOCKER_WASM,
    LAMMPS_MIGRATION_FAASM_USER,
    LAMMPS_MIGRATION_FAASM_FUNC,
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
        {
            "wasm_file": LAMMPS_MIGRATION_DOCKER_WASM,
            "wasm_user": LAMMPS_MIGRATION_FAASM_USER,
            "wasm_function": LAMMPS_MIGRATION_FAASM_FUNC,
            "copies": 1,
        },
    ]

    upload_wasm(wasm_file_details)

    lammps_data_upload(ctx, ["compute"])
