from invoke import task
from tasks.util import (
    NATIVE_HOSTFILE,
    run_kubectl_cmd,
    get_pod_names_ips,
)
from subprocess import run

HOSTFILE_LOCAL_FILE = "/tmp/hostfile"
SLOTS_PER_HOST = 2


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
