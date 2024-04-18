from invoke import task
from tasks.util.compose import run_compose_cmd
from tasks.util.env import FAABRIC_EXP_IMAGE_NAME
from tasks.util.k8s import wait_for_pods
from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    get_native_mpi_namespace,
)


@task
def deploy(ctx, backend="compose", num_vms=2):
    """
    Deploy the LAMMPS native MPI setup to K8s
    """
    if backend == "k8s":
        deploy_native_mpi("openmpi", FAABRIC_EXP_IMAGE_NAME, num_vms)

        wait_for_pods(get_native_mpi_namespace("openmpi"), "run=faasm-openmpi")
    else:
        run_compose_cmd("up -d --scale worker={}".format(num_vms))


@task
def delete(ctx, backend="compose", num_vms=2):
    """
    Delete the LAMMPS native MPI setup from K8s
    """
    if backend == "k8s":
        delete_native_mpi("lammps", FAABRIC_EXP_IMAGE_NAME, num_vms)
    else:
        run_compose_cmd("down")
