from invoke import task
from os import environ
from os.path import join
from copy import copy
from subprocess import run


from tasks.util import (
    NATIVE_HOSTFILE,
    run_kubectl_cmd,
    get_pod_names_ips,
    PROJ_ROOT,
    get_docker_tag,
    push_docker_image,
)

HOSTFILE_LOCAL_FILE = "/tmp/hostfile"
SLOTS_PER_HOST = 2

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


@task
def deploy(ctx, local=False):
    """
    Deploy the native MPI setup to K8s
    """
    deploy_yml = "deployment-local.yml" if local else "deployment.yml"

    run(
        "kubectl apply -f k8s/namespace.yml",
        shell=True,
        check=True,
    )

    run(
        "kubectl apply -f k8s/{}".format(deploy_yml),
        shell=True,
        check=True,
    )


@task
def delete(ctx):
    """
    Delete the native MPI setup from K8s
    """
    # Note we don't delete the namespace as it takes a while and doesn't do any
    # harm to leave it
    run(
        "kubectl delete -f k8s/deployment.yml",
        shell=True,
        check=True,
    )


@task
def hostfile(ctx):
    """
    Set up the hostfile on the MPI native deployment
    """
    pod_names, pod_ips = get_pod_names_ips()

    with open(HOSTFILE_LOCAL_FILE, "w") as fh:
        for ip in pod_ips:
            fh.write("{} slots={}\n".format(ip, SLOTS_PER_HOST))

    # SCP the hostfile to all hosts
    for pod_name in pod_names:
        run_kubectl_cmd(
            "cp {} {}:{}".format(
                HOSTFILE_LOCAL_FILE, pod_name, NATIVE_HOSTFILE
            )
        )
