from invoke import task
from tasks.lammps.env import LAMMPS_FAASM_USER, LAMMPS_FAASM_FUNC
from tasks.lammps.data import upload as lammps_data_upload
from tasks.makespan.env import (
    LAMMPS_DOCKER_WASM,
    LAMMPS_MIGRATION_DOCKER_WASM,
    LAMMPS_FAASM_MIGRATION_FUNC,
)
from tasks.util.upload import upload_wasm


@task
def upload(ctx):
    """
    Upload the WASM files needed for the makespan experiment
    """
    wasm_file_details = [
        {
            "wasm_file": LAMMPS_DOCKER_WASM,
            "wasm_user": LAMMPS_FAASM_USER,
            "wasm_function": LAMMPS_FAASM_FUNC,
            "copies": 1,
        },
        {
            "wasm_file": LAMMPS_MIGRATION_DOCKER_WASM,
            "wasm_user": LAMMPS_FAASM_USER,
            "wasm_function": LAMMPS_FAASM_MIGRATION_FUNC,
            "copies": 1,
        },
    ]

    upload_wasm(wasm_file_details)

    # Upload LAMMPS data
    lammps_data_upload(
        ctx, ["compute", "compute-xl", "compute-xxl", "network"]
    )
