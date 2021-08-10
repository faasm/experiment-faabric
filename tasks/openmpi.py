from invoke import task
from os import environ
from os.path import join
from copy import copy
from subprocess import run

from tasks.util.env import (
    PROJ_ROOT,
    get_docker_tag,
    push_docker_image,
)


OPENMPI_IMAGE_NAME = "openmpi"
OPENMPI_DOCKERFILE = join(PROJ_ROOT, "docker", "openmpi.dockerfile")


@task(default=True)
def build(ctx, nocache=False, push=False):
    """
    Build the container image used for native openmpi
    """
    shell_env = copy(environ)
    shell_env["DOCKER_BUILDKIT"] = "1"
    img_tag = get_docker_tag(OPENMPI_IMAGE_NAME)

    cmd = [
        "docker",
        "build",
        "-f {}".format(OPENMPI_DOCKERFILE),
        "--no-cache" if nocache else "",
        "-t {}".format(img_tag),
        ".",
    ]

    cmd_str = " ".join(cmd)
    print(cmd_str)
    run(cmd_str, shell=True, check=True, cwd=PROJ_ROOT)

    if push:
        push_docker_image(img_tag)


@task
def push(ctx):
    """
    Push the container image for native openmpi
    """
    img_tag = get_docker_tag(OPENMPI_IMAGE_NAME)
    push_docker_image(img_tag)
