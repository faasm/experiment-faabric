from invoke import task
from os.path import join
from requests import put
from subprocess import CalledProcessError, run
from tasks.makespan.env import (
    DGEMM_DOCKER_WASM,
    DGEMM_FAASM_USER,
    DGEMM_FAASM_FUNC,
    LULESH_DOCKER_WASM,
    LULESH_FAASM_USER,
    LULESH_FAASM_FUNC,
    MAKESPAN_IMAGE_NAME,
)
from tasks.util.env import PROJ_ROOT, get_version
from tasks.util.faasm import get_faasm_upload_host_port


@task(default=True)
def upload(ctx):
    """
    Upload the OpenMP functions to Granny
    """
    # TODO: remove duplication with makespan experiment!
    def start_container(image_name):
        """
        Start build container in the background
        """
        docker_cmd = [
            "docker run -d",
            "--name {}".format(tmp_image_name),
            "faasm/{}:{}".format(MAKESPAN_IMAGE_NAME, get_version()),
        ]
        docker_cmd = " ".join(docker_cmd)
        print(docker_cmd)
        run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)

    def stop_container(image_name):
        docker_cmd = "docker rm -f {}".format(tmp_image_name)
        print(docker_cmd)
        run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)

    tmp_image_name = "granny_build_container"
    # First, start the build container
    start_container(tmp_image_name)

    # TODO: eventually pass this as an argument to the shared function
    wasm_file_details = [
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
            "copies": 1,
        },
    ]

    # Upload wasm
    tmp_host_wasm = "/tmp/function.wasm"
    docker_cp_cmd = "docker cp {}:{} {}"
    for file_details in wasm_file_details:
        try:
            run(
                docker_cp_cmd.format(
                    tmp_image_name, file_details["wasm_file"], tmp_host_wasm
                ),
                shell=True,
                check=True,
            )
        except CalledProcessError as e:
            print(
                "Caught error copying WASM file from docker image: {}".format(
                    e
                )
            )
            stop_container(tmp_image_name)
            raise e

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
            if response.status_code != 200:
                print("Error! Upload failed, check the upload pod logs")
                stop_container(tmp_image_name)

    # Lastly, remove the container
    stop_container(tmp_image_name)
