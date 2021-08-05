from invoke import task
from tasks.util import (
    PROJ_ROOT,
)
from subprocess import run, PIPE

HOSTFILE_LOCAL_FILE = "/tmp/hostfile"
SLOTS_PER_HOST = 2


def _run_kubectl_cmd(cmd):
    print(cmd)
    res = run(
        cmd,
        stdout=PIPE,
        stderr=PIPE,
        cwd=PROJ_ROOT,
        shell=True,
        check=True,
    )

    return res.stdout.decode("utf-8")


@task(default=True)
def deploy(ctx, local=False):
    """
    Deploy the native MPI setup to K8s
    """
    deploy_yml = "deployment-local.yml" if local else "deployment.yml"
    _run_kubectl_cmd("kubectl apply -f k8s/namespace.yml")
    _run_kubectl_cmd("kubectl apply -f k8s/{}".format(deploy_yml))


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
    cmd_out = _run_kubectl_cmd("kubectl get pods -n faasm-mpi-native -o wide")
    print(cmd_out)

    # Split output into list of strings
    lines = cmd_out.split("\n")[1:]
    lines = [l.strip() for l in lines if l.strip()]

    # Extract pod names and IPs
    pod_names = list()
    pod_ips = list()
    for line in lines:
        line_parts = line.split(" ")
        line_parts = [p.strip() for p in line_parts if p.strip()]

        pod_names.append(line_parts[0])
        pod_ips.append(line_parts[5])

    print("Got pods: {}".format(pod_names))
    print("Got IPs: {}".format(pod_ips))

    with open(HOSTFILE_LOCAL_FILE, "w") as fh:
        for ip in pod_ips:
            fh.write("{} slots={}\n".format(ip, SLOTS_PER_HOST))

    # SCP the hostfile to all hosts
    for pod_name in pod_names:
        _run_kubectl_cmd(
            "kubectl -n faasm-mpi-native cp {} {}:/home/mpirun/hostfile".format(
                HOSTFILE_LOCAL_FILE, pod_name
            )
        )
