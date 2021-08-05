from invoke import task
from tasks.util import PROJ_ROOT, get_docker_tag, push_docker_image
from os import environ
from os.path import join
from copy import copy
from subprocess import run

LAMMPS_IMAGE_NAME = "experiment-lammps"
LAMMPS_DOCKERFILE = join(PROJ_ROOT, "docker", "lammps.dockerfile")


@task(default=True)
def build(ctx, nocache=False, push=False):
    """
    Build the container image used for LAMMPS experiment
    """
    shell_env = copy(environ)
    shell_env["DOCKER_BUILDKIT"] = "1"
    img_tag = get_docker_tag(LAMMPS_IMAGE_NAME)

    cmd = [
        "docker",
        "build",
        "-f {}".format(LAMMPS_DOCKERFILE),
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
    Push the LAMMPS container image
    """
    img_tag = get_docker_tag(LAMMPS_IMAGE_NAME)
    push_docker_image(img_tag)
