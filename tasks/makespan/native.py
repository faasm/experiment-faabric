from invoke import task
from os.path import join
from subprocess import run

from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    generate_native_mpi_hostfile,
)
from tasks.makespan.env import (
    MAKESPAN_DIR,
    MAKESPAN_IMAGE_NAME,
    MIGRATE_NATIVE_BINARY,
)

# TODO - all these tasks must eventually include the migration task


@task(default=True)
def build(ctx, clean=False, verbose=False):
    """
    Build the native migration kernel
    """
    clang_cmd = "clang++-10 mpi_migrate.cpp -lmpi -o {}".format(
        MIGRATE_NATIVE_BINARY
    )
    print(clang_cmd)
    run(clang_cmd, check=True, shell=True, cwd=MAKESPAN_DIR)


@task
def deploy(ctx, local=False):
    """
    Deploy the native MPI setup to K8s
    """
    deploy_native_mpi("makespan", MAKESPAN_IMAGE_NAME)


@task
def delete(ctx):
    """
    Delete the native MPI setup from K8s
    """
    delete_native_mpi("makespan", MAKESPAN_IMAGE_NAME)


@task
def hostfile(ctx, slots):
    """
    Set up the native MPI hostfile
    """
    generate_native_mpi_hostfile("makespan", slots=slots)
