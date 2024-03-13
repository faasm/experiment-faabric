from invoke import task
from tasks.util.env import FAABRIC_EXP_IMAGE_NAME
from tasks.util.openmpi import deploy_native_mpi, delete_native_mpi


@task
def deploy(ctx, backend="k8s", num_vms=1):
    """
    Deploy the native OpenMP k8s cluster
    """
    if backend == "k8s":
        deploy_native_mpi("openmp", FAABRIC_EXP_IMAGE_NAME, num_vms)
    else:
        raise RuntimeError("Backend not supported: {}!".format(backend))


@task
def delete(ctx, backend="k8s", num_vms=1):
    """
    Deploy the native OpenMP k8s cluster
    """
    if backend == "k8s":
        delete_native_mpi("openmp", FAABRIC_EXP_IMAGE_NAME, num_vms)
    else:
        raise RuntimeError("Backend not supported: {}!".format(backend))
