# LULESH Experiment

This experiment is a single execution of the LULESH simulation using OpenMP.

## Start AKS cluster

In the `experiment-base` terminal, run:

```bash
(faasm-exp-base) inv cluster.provision --vm Standard_D8_v5 --nodes 1
(faasm-exp-base) inv cluster.credentials
```

## Granny

Deploy the cluster:

```bash
(faasm-exp-faabric) faasmctl deploy.k8s --workers=1
```

Upload the WASM file:

```bash
(faasm-exp-faabric) inv lammps.wasm.upload
```

and run the experiment with:

```bash
(faasm-exp-faabric) inv lammps.run.granny -w compute -w network
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
inv lammps.run.native -w compute -w network
```

finally, delete the native cluster:

```bash
inv lammps.native.delete
```

# Plot

To plot the results, you may run:

```bash
inv lammps.plot
```

which will generate a plot in [`./plots/lammps/runtime.png`](
./plots/lammps/runtime.png), we also include it below:

![LAMMPS Runtime Plot](./plots/lammps/runtime.png)

## Clean-Up

Remember to delete the cluster. From the experiment base terminal:

```bash
inv cluster.delete
```
