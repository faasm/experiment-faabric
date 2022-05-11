from invoke import task
from os.path import join
from subprocess import run

from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    generate_native_mpi_hostfile,
)
from tasks.lammps.env import (
    LAMMPS_IMAGE_NAME,
)

# TODO - all these tasks must eventually include the migration task


@task
def deploy(ctx, local=False):
    """
    Deploy the native MPI setup to K8s
    """
    deploy_native_mpi("lammps", LAMMPS_IMAGE_NAME)


@task
def delete(ctx):
    """
    Delete the native MPI setup from K8s
    """
    delete_native_mpi("lammps", LAMMPS_IMAGE_NAME)


@task
def hostfile(ctx, slots):
    """
    Set up the native MPI hostfile
    """
    generate_native_mpi_hostfile("lammps", slots=slots)
