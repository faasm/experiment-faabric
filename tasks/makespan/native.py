from invoke import task
from subprocess import run
from tasks.makespan.env import (
    DOCKER_MIGRATE_BINARY,
    MAKESPAN_DIR,
    MAKESPAN_NATIVE_DIR,
    MAKESPAN_IMAGE_NAME,
)
from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    generate_native_mpi_hostfile,
)


@task(default=True)
def build(ctx, clean=False, verbose=False):
    """
    Build the native migration kernel (run inside the container)
    """
    clang_cmd = "clang++-10 mpi_migrate.cpp -lmpi -o {}".format(
        DOCKER_MIGRATE_BINARY
    )
    print(clang_cmd)
    run(clang_cmd, check=True, shell=True, cwd=MAKESPAN_NATIVE_DIR)


@task
def deploy(ctx, num_nodes=4, local=False):
    """
    Deploy the native MPI setup to K8s (or compose with --local flag)
    """
    if not local:
        num_nodes = int(num_nodes)
        deploy_native_mpi("makespan", MAKESPAN_IMAGE_NAME, num_nodes)
    else:
        compose_cmd = [
            "docker compose",
            "up -d",
            "--scale worker={}".format(num_nodes),
        ]
        compose_cmd = " ".join(compose_cmd)
        run(compose_cmd, shell=True, check=True, cwd=MAKESPAN_DIR)


@task
def delete(ctx, num_nodes):
    """
    Delete the native MPI setup from K8s
    """
    delete_native_mpi("makespan", MAKESPAN_IMAGE_NAME, num_nodes)


@task
def hostfile(ctx, slots):
    """
    Set up the native MPI hostfile
    """
    generate_native_mpi_hostfile("makespan", slots=slots)
