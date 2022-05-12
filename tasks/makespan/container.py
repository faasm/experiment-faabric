from invoke import task
from os import environ
from copy import copy
from subprocess import run

from tasks.util.env import (
    PROJ_ROOT,
    get_docker_tag,
    get_version,
    push_docker_image,
)
from tasks.makespan.env import MAKESPAN_IMAGE_NAME, MAKESPAN_DOCKERFILE


@task(default=True)
def build(ctx, nocache=False, push=False):
    """
    Build the container image used for LAMMPS experiment
    """
    shell_env = copy(environ)
    shell_env["DOCKER_BUILDKIT"] = "1"
    img_tag = get_docker_tag(MAKESPAN_IMAGE_NAME)

    cmd = [
        "docker",
        "build",
        "-f {}".format(MAKESPAN_DOCKERFILE),
        "--no-cache" if nocache else "",
        "--build-arg EXPERIMENT_VERSION={}".format(get_version()),
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
    Push the LAMMPS container image
    """
    img_tag = get_docker_tag(MAKESPAN_IMAGE_NAME)
    push_docker_image(img_tag)
