from faasmctl.util.upload import (
    upload_file as faasmctl_upload_file,
    upload_wasm as faasmctl_upload_wasm,
)
from subprocess import CalledProcessError, run
from tasks.util.env import (
    ACR_NAME,
    FAABRIC_EXP_IMAGE_NAME,
    PROJ_ROOT,
    get_version,
)

TMP_IMAGE_NAME = "granny_build_container"


def start_container(image_name):
    """
    Start build container in the background
    """
    docker_cmd = [
        "docker run -d",
        "--name {}".format(TMP_IMAGE_NAME),
        "{}/{}:{}".format(ACR_NAME, FAABRIC_EXP_IMAGE_NAME, get_version()),
    ]
    docker_cmd = " ".join(docker_cmd)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)


def stop_container(image_name):
    docker_cmd = "docker rm -f {}".format(TMP_IMAGE_NAME)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)


def upload_wasm(wasm_file_details):
    """
    Upload WASM files to a Granny deployment

    Given a dictionary with the files to upload, and the number of copies. This
    method copies the .wasm files from the `experiment-makespan` docker image
    """
    # First, start the build container
    start_container(TMP_IMAGE_NAME)

    # Upload wasm
    tmp_host_wasm = "/tmp/function.wasm"
    docker_cp_cmd = "docker cp {}:{} {}"
    for file_details in wasm_file_details:
        try:
            run(
                docker_cp_cmd.format(
                    TMP_IMAGE_NAME, file_details["wasm_file"], tmp_host_wasm
                ),
                shell=True,
                check=True,
            )
            print("Success:", file_details["wasm_file"])
        except CalledProcessError as e:
            print(
                "Caught error copying WASM file from docker image: {}".format(
                    e
                )
            )
            stop_container(TMP_IMAGE_NAME)
            raise e

        wasm_file = tmp_host_wasm
        user = file_details["wasm_user"]
        for i in range(file_details["copies"]):
            if file_details["copies"] > 1:
                func = "{}_{}".format(file_details["wasm_function"], i)
            else:
                func = file_details["wasm_function"]
            try:
                faasmctl_upload_wasm(user, func, wasm_file)
            except Exception as e:
                print(e)
                stop_container(TMP_IMAGE_NAME)

    # Lastly, remove the container
    stop_container(TMP_IMAGE_NAME)


def upload_files(file_details):
    """
    Upload WASM files to a Granny deployment

    Given a dictionary with the host and faasm paths of the files to upload,
    this method copies the files from the `experiment-granny` docker image and
    uploads them to the cluster
    """
    # First, start the build container
    start_container(TMP_IMAGE_NAME)

    # Upload wasm
    tmp_host_file = "/tmp/faasm.file"
    docker_cp_cmd = "docker cp {}:{} {}"
    for file_details in file_details:
        try:
            run(
                docker_cp_cmd.format(
                    TMP_IMAGE_NAME, file_details["host_path"], tmp_host_file
                ),
                shell=True,
                check=True,
            )
            print("Success:", file_details["wasm_file"])
        except CalledProcessError as e:
            print(
                "Caught error copying WASM file from docker image: {}".format(
                    e
                )
            )
            stop_container(TMP_IMAGE_NAME)
            raise e

        try:
            faasmctl_upload_file(tmp_host_file, file_details["faasm_path"])
        except Exception as e:
            print(e)
            stop_container(TMP_IMAGE_NAME)

    # Lastly, remove the container
    stop_container(TMP_IMAGE_NAME)
