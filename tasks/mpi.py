from invoke import task
from tasks.util import (
    PROJ_ROOT,
)
from subprocess import run

HOSTFILE_LOCAL_FILE = "/tmp/hostfile"


def _run_kubectl_cmd(cmd):
    print(cmd)
    return run(
        cmd,
        cwd=PROJ_ROOT,
        shell=True,
        check=True,
    )


@task(default=True)
def deploy(ctx):
    """
    Deploy the native MPI setup to K8s
    """
    _run_kubectl_cmd("kubectl apply -f k8s/namespace.yml")
    _run_kubectl_cmd("kubectl apply -f k8s/deployment.yml")


@task
def delete(ctx):
    """
    Delete the native MPI setup from K8s
    """
    # Note we don't delete the namespace as it takes a while and doesn't do any
    # harm to leave it
    _run_kubectl_cmd("kubectl delete -f k8s/deployment.yml")


@task
def hostfile(ctx):
    """
    Set up the hostfile on the MPI native deployment
    """
    res = _run_kubectl_cmd(
        "kubectl get pods -n mpi-native -l run=mpi-native -o wide"
    )

    print("kubectl result: {}".format(res.stdout))

    hosts = list()

    # TODO - parse list of hosts

    with open(HOSTFILE_LOCAL_FILE, "w") as fh:
        # TODO write results
        pass

    # SCP it to all hosts
    for host in hosts:
        _run_kubectl_cmd(
            "kubectl cp {} mpi-native/{}:/home/mpirun/hostfile".format(
                HOSTFILE_LOCAL_FILE, host
            )
        )
