from invoke import task

from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    generate_native_mpi_hostfile,
)
from tasks.kernels.env import KERNELS_IMAGE_NAME


@task
def deploy(ctx, local=False):
    """
    Deploy the Kernels native MPI setup to K8s
    """
    deploy_native_mpi("kernels", KERNELS_IMAGE_NAME)


@task
def delete(ctx):
    """
    Delete the Kernels native MPI setup from K8s
    """
    delete_native_mpi("kernels", KERNELS_IMAGE_NAME)


@task
def hostfile(ctx):
    """
    Set up the Kernels native MPI hostfile
    """
    generate_native_mpi_hostfile("kernels")
