import requests

from invoke import task
from os.path import join
from tasks.lammps.wasm import upload as lammps_upload
from tasks.lammps.data import upload as lammps_data_upload
from tasks.makespan.env import (
    MAKESPAN_IMAGE_NAME,
    MAKESPAN_WASM_DIR,
    MIGRATE_FAASM_USER,
    MIGRATE_FAASM_FUNC,
)
from tasks.util.env import PROJ_ROOT, get_version, WASM_INSTALL_DIR
from tasks.util.faasm import get_faasm_upload_host_port
from subprocess import run


@task
def build(ctx):
    """
    Build the WASM functions needed for the makespan experiment: mpi/migration,
    and lammps/main
    """
    tmp_image_name = "granny_build_container"
    # First, start the container in the background
    docker_cmd = [
        "docker run -d",
        "-v {}:/code/experiment-mpi".format(PROJ_ROOT),
        "--name {}".format(tmp_image_name),
        "faasm/{}:{}".format(MAKESPAN_IMAGE_NAME, get_version()),
    ]
    docker_cmd = " ".join(docker_cmd)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)

    # Second, build the wasm for LAMMPS
    docker_cmd = [
        "docker exec",
        tmp_image_name,
        "inv lammps.wasm",
    ]
    docker_cmd = " ".join(docker_cmd)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)

    # Third, build the wasm for the migrate function
    docker_cmd = [
        "docker cp",
        join(MAKESPAN_WASM_DIR, "mpi_migrate.cpp"),
        "{}:/code/cpp/func/mpi/migrate.cpp".format(tmp_image_name),
    ]
    docker_cmd = " ".join(docker_cmd)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)
    docker_cmd = [
        "docker exec",
        "--workdir /code/cpp",
        tmp_image_name,
        "inv func mpi migrate",
    ]
    docker_cmd = " ".join(docker_cmd)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)
    docker_cmd = [
        "docker cp",
        "{}:/code/cpp/build/func/mpi/migrate.wasm".format(tmp_image_name),
        join(MAKESPAN_WASM_DIR, "migrate.wasm"),
    ]
    docker_cmd = " ".join(docker_cmd)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)

    # Lastly, remove the container
    docker_cmd = "docker rm -f {}".format(tmp_image_name)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)


@task
def upload(ctx):
    """
    Upload the two functions and two pieces of input data needed for the
    experiment
    """
    # Upload LAMMPS wasm
    lammps_upload(ctx)

    # Upload LAMMPS data
    lammps_data_upload(ctx, ["compute", "network"])

    # Migration wasm file
    wasm_file = join(MAKESPAN_WASM_DIR, "migrate.wasm")
    host, port = get_faasm_upload_host_port()
    url = "http://{}:{}/f/{}/{}".format(
        host, port, MIGRATE_FAASM_USER, MIGRATE_FAASM_FUNC
    )
    print("Putting function to {}".format(url))
    response = requests.put(url, data=open(wasm_file, "rb"))
    print("Response {}: {}".format(response.status_code, response.text))
