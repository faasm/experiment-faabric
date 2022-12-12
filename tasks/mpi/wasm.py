from invoke import task
from os.path import join
from tasks.lammps.data import upload as lammps_data_upload
from tasks.util.env import (
    KERNELS_FAASM_FUNCS,
    KERNELS_FAASM_USER,
    KERNELS_WASM_DIR,
    LAMMPS_DOCKER_WASM,
    LAMMPS_FAASM_USER,
    LAMMPS_FAASM_FUNC,
)
from tasks.util.upload import upload_wasm


@task()
def upload(ctx):
    """
    Upload the MPI functions to Granny
    """
    wasm_file_details = [
        {
            "wasm_file": LAMMPS_DOCKER_WASM,
            "wasm_user": LAMMPS_FAASM_USER,
            "wasm_function": LAMMPS_FAASM_FUNC,
            "copies": 1,
        },
    ]

    for kernel in KERNELS_FAASM_FUNCS:
        wasm_file_details.append(
            {
                "wasm_file": join(
                    KERNELS_WASM_DIR, "mpi_{}.wasm".format(kernel)
                ),
                "wasm_user": KERNELS_FAASM_USER,
                "wasm_function": kernel,
                "copies": 1,
            }
        )

    upload_wasm(wasm_file_details)

    # LAMMPS also needs some extra data files
    lammps_data_upload(
        ctx, ["compute", "compute-xl", "compute-xxl", "network"]
    )
