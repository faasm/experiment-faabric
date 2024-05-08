# Elastic Scaling Micro-Benchmark

In this experiment we measure the benefits of elastically scaling-up OpenMP
applications to benefit from idle resources. We run a pipe-lined algorithm
on a matrix with a varying number of threads, and at 50% of execution we
scale-up to the maximum number of available threads. This plot is a best-case
scenario for the benefits we can get by elastically scaling-up.

## Granny

First, start the AKS cluster by running:

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 2 cluster.credentials
```

Second, deploy the Granny cluster:

```bash
faasmctl deploy.k8s --workers=1
```

Third, upload the WASM file:

```bash
inv elastic.wasm.upload
```

and run the experiment with:

```bash
# Without elastic scaling
inv elastic.run

# With elastic scaling
inv elastic.run --elastic
```

## Plot

You may now plot the results using:

```bash
inv elastic.plot
```

## Clean-Up

Finally, delete the Granny cluster:

```bash
faasmctl delete
```

and the AKS cluster:

```bash
inv cluster.delete
```
