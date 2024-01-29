# LAMMPS Experiment

This experiment is a single execution of the LAMMPS simulation stress tested
as part of the array experiment.

## Start AKS cluster

In the `experiment-base` terminal, run:

```bash
(faasm-exp-base) inv cluster.provision --vm Standard_D8_v5 --nodes 2
(faasm-exp-base) inv cluster.credentials
```

## Granny

Deploy the cluster, and point an env. var to the cluster deployment file:

```bash
(faasm-exp-faabric) faasmctl deploy.k8s --workers=2
```

Upload the WASM file:

```bash
(faasm-exp-faabric) inv lammps.wasm.upload
```

and run the experiment with:

```bash
(faasm-exp-faabric) inv lammps.run.granny
```

To remove the cluster, run:

```bash
(faasm-exp-mpi) faasmctl delete
```

## Native

Deploy the cluster:

```bash
inv lammps.native.deploy
```

And run:

```bash
inv lammps.run.native
```

# Plot

TODO:

## Clean-Up

Remember to delete the cluster. From the experiment base terminal:

```bash
inv cluster.delete
```
