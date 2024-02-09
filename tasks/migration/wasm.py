from invoke import task
from tasks.util.env import (
    MPI_MIGRATE_WASM_BINARY,
    MPI_MIGRATE_FAASM_USER,
    MPI_MIGRATE_FAASM_FUNC,
)
from tasks.util.lammps import (
    LAMMPS_MIGRATION_DOCKER_WASM,
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_MIGRATION_NET_FUNC,
    lammps_data_upload,
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
            "wasm_user": LAMMPS_FAASM_USER,
            "wasm_function": LAMMPS_FAASM_MIGRATION_NET_FUNC,
            "copies": 1,
        },
    ]

    upload_wasm(wasm_file_details)

    lammps_data_upload(ctx, ["compute", "compute-xl", "network"])
