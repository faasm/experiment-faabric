from invoke import task
from os import environ
from os.path import join
from copy import copy
from subprocess import run

from tasks.util import get_docker_tag, push_docker_image, PROJ_ROOT

KERNELS_IMAGE_NAME = "experiment-kernels"
KERNELS_DOCKERFILE = join(PROJ_ROOT, "docker", "kernels.dockerfile")


@task(default=True)
def build(ctx, nocache=False, push=False):
    """
    Build the container image used for kernels experiment
    """
    shell_env = copy(environ)
    shell_env["DOCKER_BUILDKIT"] = "1"
    img_tag = get_docker_tag(KERNELS_IMAGE_NAME)

    cmd = [
        "docker",
        "build",
        "-f {}".format(KERNELS_DOCKERFILE),
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
    Push the kernels container image
    """
    img_tag = get_docker_tag(KERNELS_IMAGE_NAME)
    push_docker_image(img_tag)
