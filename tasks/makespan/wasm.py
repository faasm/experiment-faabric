from invoke import task
from requests import put
from tasks.lammps.env import LAMMPS_FAASM_USER, LAMMPS_FAASM_FUNC
from tasks.lammps.data import upload as lammps_data_upload
from tasks.makespan.env import (
    DGEMM_DOCKER_WASM,
    DGEMM_FAASM_USER,
    DGEMM_FAASM_FUNC,
    LAMMPS_DOCKER_WASM,
    LULESH_DOCKER_WASM,
    LULESH_FAASM_USER,
    LULESH_FAASM_FUNC,
    MAKESPAN_IMAGE_NAME,
)
from tasks.util.env import PROJ_ROOT, get_version
from tasks.util.faasm import get_faasm_upload_host_port
from subprocess import run


@task
def upload(ctx):
    """
    Upload the two functions and two pieces of input data needed for the
    experiment
    """
    tmp_image_name = "granny_build_container"

    # First, start the container in the background
    docker_cmd = [
        "docker run -d",
        "--name {}".format(tmp_image_name),
        "faasm/{}:{}".format(MAKESPAN_IMAGE_NAME, get_version()),
    ]
    docker_cmd = " ".join(docker_cmd)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)

    # TODO: re-use the path from somewhere
    wasm_file_details = [
        {
            "wasm_file": LAMMPS_DOCKER_WASM,
            "wasm_user": LAMMPS_FAASM_USER,
            "wasm_function": LAMMPS_FAASM_FUNC,
            "copies": 1,
        },
        {
            "wasm_file": LULESH_DOCKER_WASM,
            "wasm_user": LULESH_FAASM_USER,
            "wasm_function": LULESH_FAASM_FUNC,
            "copies": 1,
        },
        {
            "wasm_file": DGEMM_DOCKER_WASM,
            "wasm_user": DGEMM_FAASM_USER,
            "wasm_function": DGEMM_FAASM_FUNC,
            "copies": 100,
        },
    ]

    # Upload wasm
    tmp_host_wasm = "/tmp/function.wasm"
    docker_cp_cmd = "docker cp {}:{} {}"
    for file_details in wasm_file_details:
        run(
            docker_cp_cmd.format(
                tmp_image_name, file_details["wasm_file"], tmp_host_wasm
            ),
            shell=True,
            check=True,
        )
        wasm_file = tmp_host_wasm
        user = file_details["wasm_user"]
        host, port = get_faasm_upload_host_port()
        for i in range(file_details["copies"]):
            if file_details["copies"] > 1:
                func = "{}_{}".format(file_details["wasm_function"], i)
            else:
                func = file_details["wasm_function"]
            url = "http://{}:{}/f/{}/{}".format(host, port, user, func)
            print("Putting function {}/{} to {}".format(user, func, url))
            response = put(url, data=open(wasm_file, "rb"))
            print(
                "Response {}: {}".format(response.status_code, response.text)
            )

    # Upload LAMMPS data
    lammps_data_upload(
        ctx, ["compute", "compute-xl", "compute-xxl", "network"]
    )

    # Lastly, remove the container
    docker_cmd = "docker rm -f {}".format(tmp_image_name)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)
