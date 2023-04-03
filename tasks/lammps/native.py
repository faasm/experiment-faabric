from invoke import task
from tasks.util.env import FAABRIC_EXP_IMAGE_NAME
from tasks.util.k8s import wait_for_pods
from tasks.util.openmpi import (
    deploy_native_mpi,
    delete_native_mpi,
    generate_native_mpi_hostfile,
    get_native_mpi_namespace,
)


@task
def deploy(ctx, backend="k8s", num_vms=2, num_cores_per_vm=8, ctrs_per_vm=1):
    """
    Deploy the LAMMPS native MPI setup to K8s
    """
    num_ctrs = int(num_vms) * int(ctrs_per_vm)
    num_cores_per_ctr = int(num_cores_per_vm / ctrs_per_vm)
    if backend == "k8s":
        deploy_native_mpi(
            "lammps", FAABRIC_EXP_IMAGE_NAME, num_ctrs, num_cores_per_ctr
        )

        wait_for_pods(get_native_mpi_namespace("lammps"), "run=faasm-openmpi")
        generate_native_mpi_hostfile("lammps", slots=num_cores_per_ctr)
    else:
        raise RuntimeError("Compose backend not implemented!")


@task
def delete(ctx, backend="k8s", num_vms=2, num_cores_per_vm=8, ctrs_per_vm=1):
    """
    Delete the LAMMPS native MPI setup from K8s
    """
    num_ctrs = int(num_vms) * int(ctrs_per_vm)
    num_cores_per_ctr = int(num_cores_per_vm / ctrs_per_vm)

    if backend == "k8s":
        delete_native_mpi(
            "lammps", FAABRIC_EXP_IMAGE_NAME, num_ctrs, num_cores_per_ctr
        )
    else:
        raise RuntimeError("Compose backend not implemented!")
