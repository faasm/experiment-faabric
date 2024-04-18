from invoke import task
from tasks.util.lammps import (
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_MIGRATION_NET_FUNC,
    LAMMPS_MIGRATION_NET_DOCKER_WASM,
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
            "wasm_file": LAMMPS_MIGRATION_NET_DOCKER_WASM,
            "wasm_user": LAMMPS_FAASM_USER,
            "wasm_function": LAMMPS_FAASM_MIGRATION_NET_FUNC,
            "copies": 1,
        },
    ]

    upload_wasm(wasm_file_details)

    lammps_data_upload(ctx, ["compute", "compute-xl", "network"])
