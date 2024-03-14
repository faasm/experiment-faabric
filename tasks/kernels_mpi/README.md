# ParRes Kernels Experiment (MPI)

This experiment runs a set of the [ParRes Kernels](https://github.com/ParRes/Kernels)
as a microbenchmark for Granny's MPI implementation.

## Start AKS cluster

In the `experiment-base` terminal, run:

```bash
(faasm-exp-base) inv cluster.provision --vm Standard_D8_v5 --nodes 3 cluster.credentials
```

## Granny

Deploy the cluster:

```bash
(faasm-exp-faabric) faasmctl deploy.k8s --workers=2
```

Upload the WASM file:

```bash
(faasm-exp-faabric) inv kernels-mpi.wasm.upload
```

and run the experiment with:

```bash
(faasm-exp-faabric) inv kernels-mpi.run.granny
```

finally, delete the Granny cluster:

```bash
faasmctl delete
```

## OpenMPI

Deploy the OpenMPI cluster:

```bash
inv kernels-mpi.native.deploy
```

```bash
inv kernels-mpi.run.native
```

finally, delete the OpenMPI cluster

```bash
inv kernels-mpi.native.delete
```

## Plot

To plot the results, just run:

```bash
inv kernels-mpi.plot
```

the plot will be available in [`./plots/kernels-mpi/mpi_kernels_slowdown.pdf`](
./plots/kernels-mpi/mpi_kernels_slowdown.pdf), we also include it below:

![MPI Kernels Slowdown Plot](./plots/kernels-mpi/mpi_kernels_slowdown.png)

## Clean-up

Finally, delete the AKS cluster:

```bash
(faasm-exp-base) inv cluster.delete
```
