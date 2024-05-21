from invoke import task
from tasks.util.env import FAABRIC_EXP_IMAGE_NAME
from tasks.util.k8s import wait_for_pods
from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    get_native_mpi_namespace,
)


@task
def deploy(ctx, backend="k8s", num_vms=2):
    """
    Deploy the Kernels native MPI setup to K8s
    """
    if backend == "k8s":
        deploy_native_mpi("kernels", FAABRIC_EXP_IMAGE_NAME, num_vms)

        wait_for_pods(
            get_native_mpi_namespace("kernels"),
            "run=faasm-openmpi",
            num_expected=num_vms,
        )
    else:
        raise RuntimeError("Compose backend not implemented!")


@task
def delete(ctx, backend="k8s", num_vms=2):
    """
    Delete the LAMMPS native MPI setup from K8s
    """
    if backend == "k8s":
        delete_native_mpi("kernels", FAABRIC_EXP_IMAGE_NAME, num_vms)
    else:
        raise RuntimeError("Compose backend not implemented!")
