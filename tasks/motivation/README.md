# Motivation figure

In this document we list the instructions to reproduce the motivation figure
we use to argue that OpenMPI underutilises the cluster resources.

## Set-up

First, from the `exp-base` shell, deploy the VM cluster:

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 32
inv cluster.credentials
```

## Run baselines

Now, back to the experiments shell, provision the native K8s cluster:

```bash
inv makespan.native.deploy
```

Then, you can run both baselines:

```bash
inv makespan.run.native-slurm --workload mpi
inv makespan.run.native-batch --workload mpi
```

## Plot

To generate the plot, run:

```bash
inv motivation.plot
```

this will generate a PDF plot in [`./plots/motivation/motivation.pdf`](./plots/motivation/motivation.pdf).
