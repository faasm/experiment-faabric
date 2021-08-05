from invoke import task
from tasks.util import PROJ_ROOT, get_version
from os import environ
from copy import copy
from subprocess import run

IMAGE_NAME = "experiment-lammps"


def _get_tag():
    img_tag = "faasm/{}:{}".format(IMAGE_NAME, get_version())
    return img_tag


def _push_image(img_tag):
    run("docker push {}".format(img_tag), check=True, shell=True)


@task(default=True)
def build(ctx, nocache=False, push=False):
    """
    Build the container image used for LAMMPS experiment
    """
    shell_env = copy(environ)
    shell_env["DOCKER_BUILDKIT"] = "1"
    img_tag = _get_tag()

    cmd = [
        "docker",
        "build",
        "--no-cache" if nocache else "",
        "-t {}".format(img_tag),
        ".",
    ]

    cmd_str = " ".join(cmd)
    print(cmd_str)
    run(cmd_str, shell=True, check=True, cwd=PROJ_ROOT)

    if push:
        _push_image(img_tag)


@task
def push(ctx):
    """
    Push the container image
    """
    img_tag = _get_tag()
    _push_image(img_tag)
