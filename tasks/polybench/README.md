# PolyBench/C Microbenchmark

This experiment explores the baseline overheads of using WebAssembly instead
of native x86 execution. We execute the [PolyBench/C](
https://web.cse.ohio-state.edu/~pouchet.2/software/polybench/) benchmark; a
set of basic C kernels, and report the slowdown of WASM execution (using
Granules) compared to native x86 execution.

## Hardware Provisioning

First, provision the cluster. For ease of deployment, we still deploy a K8s
cluster of just one node, which we will access directly.

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 1 --name ${CLUSTER_NAME}
inv cluster.credentials --name ${CLUSTER_NAME}
```

## Native

Deploy the native baseline:

```bash
inv polybench.native.deploy
```

And run it:

```bash
inv polybench.run.native
```

To delete the `k8s` cluster run:

```bash
inv polybench.native.delete
```

## Granny

First, deploy the K8s cluster:

```bash
cd ~/faasm
source ./bin/workon.sh
WASM_VM=wamr inv k8s.deploy --workers 1
```

Second, upload the WASM files:

```bash
inv polybench.wasm.upload
```

Third, run the experiments:

```bash
inv polybench.run.granny
```

To remove the cluster run:

```bash
cd ~/faasm
source ./bin/workon.sh
inv k8s.delete
```

## Plotting the results

To plot the results you may run:

```bash
inv polybench.plot
```

which will generate a `.pdf` file in `./plots/polybench/slowdown.pdf`.

## Hardware Cleanup

Lastly, clean the cluster:

```bash
inv cluster.delete --name ${CLUSTER_NAME}
```
