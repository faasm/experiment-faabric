# Motivation figure

In this document we list the instructions to reproduce the motivation figure
we use to argue that OpenMPI underutilises the cluster resources.

## Set-up

First, deploy the VM cluster:

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 32
inv cluster.credentials
```

## Run baselines

First, run the `slurm` baseline:

```bash
# TODO: move --ctrs-per-vm to `slurm` or `batch`
inv makespan.native.deploy --ctrs-per-vm 8
```

