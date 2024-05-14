from invoke import task
from tasks.util.elastic import (
    OPENMP_ELASTIC_FUNCTION,
    OPENMP_ELASTIC_USER,
    OPENMP_ELASTIC_WASM,
)
from tasks.util.lammps import (
    LAMMPS_FAASM_USER,
    LAMMPS_MIGRATION_NET_DOCKER_WASM,
    LAMMPS_FAASM_MIGRATION_NET_FUNC,
    lammps_data_upload,
)
from tasks.util.upload import upload_wasm


@task
def upload(ctx):
    """
    Upload the WASM files needed for the makespan experiment
    """
    wasm_file_details = [
        {
            "wasm_file": LAMMPS_MIGRATION_NET_DOCKER_WASM,
            "wasm_user": LAMMPS_FAASM_USER,
            "wasm_function": LAMMPS_FAASM_MIGRATION_NET_FUNC,
            "copies": 1,
        },
        {
            "wasm_file": OPENMP_ELASTIC_WASM,
            "wasm_user": OPENMP_ELASTIC_USER,
            "wasm_function": OPENMP_ELASTIC_FUNCTION,
            "copies": 1,
        },
    ]

    upload_wasm(wasm_file_details)

    # Upload LAMMPS data
    lammps_data_upload(
        ctx, ["compute", "compute-xl", "compute-xxl", "network"]
    )
