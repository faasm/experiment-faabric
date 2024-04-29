# Makespan Experiment (SPOT VM version)

First, from the `faasm-exp-base` shell, deploy the VM cluster:

```bash
# TODO: varying sizes of cluster
(faasm-exp-base) inv cluster.provision --vm Standard_D8_v5 --nodes 33
(faasm-exp-base) inv cluster.credentials
```

## Native

First, deploy the native `k8s` cluster:

```bash
(faasm-exp-base) inv makespan.native.deploy --num-vms 32
```

Now, you can run the different baselines:

```bash
(faasm-exp-base) inv makespan.run.native-batch --workload mpi-evict --num-vms 32 --num-tasks 200
(faasm-exp-base) inv makespan.run.native-slurm --workload mpi-evict --num-vms 32 --num-tasks 200
```

Lastly, remove the native `k8s` cluster:

```bash
inv makespan.native.delete
```

## Granny (MPI)

First, deploy the k8s cluster:

```bash
faasmctl deploy.k8s --workers=32
```

Second, upload the corresponding WASM files:

```bash
(faasm-exp-faabric) inv makespan.wasm.upload
```

Third, run the experiment:

```bash
# In this case the migration activates the fault-injection thread
(faasm-exp-faabric) inv makespan.run.granny --num-vms 32 --num-tasks 100 --workload mpi-spot [--fault]
```

During an experiment, you may monitor the state of the cluster (in a separete
shell) by using:

```bash
(faasm-exp-faabric) faasmctl monitor.planner
```

## Plot the results

To plot the results, just run:

```bash
# TODO: this does not work atm
# TODO: move from tasks/motivation/plot.py
inv makespan.plot.migration
```
