from invoke import task
from subprocess import run
from tasks.makespan.env import (
    MAKESPAN_DIR,
    MAKESPAN_IMAGE_NAME,
)
from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    generate_native_mpi_hostfile,
)


@task
def deploy(ctx, backend="k8s", num_vms=32, num_cores_per_vm=8, ctrs_per_vm=1):
    """
    Run: `inv makespan.native.deploy --backend --num-vms --ctrs-per-vm`
    """
    num_ctrs = int(num_vms) * int(ctrs_per_vm)
    num_cores_per_ctr = int(num_cores_per_vm / ctrs_per_vm)
    if backend == "k8s":
        deploy_native_mpi(
            "makespan", MAKESPAN_IMAGE_NAME, num_ctrs, num_cores_per_ctr
        )
    else:
        # TODO: update .env file
        compose_cmd = [
            "docker compose",
            "up -d",
            "--scale worker={}".format(num_ctrs),
        ]
        compose_cmd = " ".join(compose_cmd)
        run(compose_cmd, shell=True, check=True, cwd=MAKESPAN_DIR)


@task
def delete(ctx, backend="k8s", num_vms=32, num_cores_per_vm=8, ctrs_per_vm=1):
    """
    Delete: `inv makespan.native.delete --backend --num-vms --ctrs-per-vm
    """
    num_ctrs = int(num_vms) * int(ctrs_per_vm)
    num_cores_per_ctr = int(num_cores_per_vm / ctrs_per_vm)
    if backend == "k8s":
        delete_native_mpi(
            "makespan", MAKESPAN_IMAGE_NAME, num_ctrs, num_cores_per_ctr
        )
    else:
        compose_cmd = [
            "docker compose",
            "down",
        ]
        compose_cmd = " ".join(compose_cmd)
        run(compose_cmd, shell=True, check=True, cwd=MAKESPAN_DIR)


@task
def hostfile(ctx, slots):
    """
    Set up the native MPI hostfile
    """
    generate_native_mpi_hostfile("makespan", slots=slots)
