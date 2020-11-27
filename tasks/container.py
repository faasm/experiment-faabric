from os.path import join
from subprocess import run

from invoke import task
from tasks.util.env import EXPERIMENT_ROOT
from tasks.util.version import get_version

EXPERIMENT_IMAGE_NAME = "experiment-lammps"


def _get_docker_tag(img_name):
    ver = get_version()
    return "faasm/{}:{}".format(img_name, ver)


def _do_container_build(name, nocache=False, push=False):
    tag_name = _get_docker_tag(name)
    ver = get_version()

    if nocache:
        no_cache_str = "--no-cache"
    else:
        no_cache_str = ""

    dockerfile = join(EXPERIMENT_ROOT, "docker", "{}.dockerfile".format(name))

    build_cmd = [
        "docker build",
        no_cache_str,
        "-t {}".format(tag_name),
        "-f {}".format(dockerfile),
        "--build-arg EXPERIMENTS_VERSION={}".format(ver),
        ".",
    ]
    build_cmd = " ".join(build_cmd)

    print(build_cmd)
    run(build_cmd, shell=True, check=True, env={"DOCKER_BUILDKIT": "1"})

    if push:
        _do_push(name)


def _do_push(name):
    tag_name = _get_docker_tag(name)

    cmd = "docker push {}".format(tag_name)
    print(cmd)
    run(cmd, shell=True, check=True)


@task
def build(ctx, nocache=False, push=False):
    """
    Build current version of the base experiment container.
    """
    _do_container_build(EXPERIMENT_IMAGE_NAME, nocache=nocache, push=push)


@task
def push(ctx):
    """
    Push current version of the base experiment container.
    """
    _do_push(EXPERIMENT_IMAGE_NAME)
