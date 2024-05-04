# Makespan Experiment (SPOT VM version)

In this experiment we study the benefits of using Granules to execute a batch
of scientific applications on a cluster of intermittently available spot VMs.

For each experiment run, we increase the cluster size (in terms of number of
VMs) and the number of jobs in the tasks, proportionally.

Re-run the following instructions with the following values:

```bash
NUM_VMS=4,8,16,32
NUM_TASKS=10,25,50,100
```

## Deploy the cluster

First, to deploy the cluster, run:

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes ${NUM_VMS} + 1
inv cluster.credentials
```

## Native (OpenMPI)

First, deploy the native `k8s` cluster:

```bash
inv makespan.native.deploy --num-vms ${NUM_VMS}
```

Now, you can run the different baselines, with and without spot VMs:

```bash
# No spot VMs (aka no VM eviction)
inv makespan.run.native-batch --workload mpi-spot --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS}
inv makespan.run.native-slurm --workload mpi-spot --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS}

# Spot VMs (aka VM eviction)
inv makespan.run.native-batch --workload mpi-spot --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS} --fault
inv makespan.run.native-slurm --workload mpi-spot --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS} --fault
```

Once you are done, you may remove the native OpenMPI cluster:

```bash
inv makespan.native.delete
```

## Granny

To run the Granny baseline, first deploy the cluster:

```bash
faasmctl deploy.k8s --workers=${NUM_VMS}
```

Second, upload the corresponding WASM files:

```bash
inv makespan.wasm.upload
```

Third, run the experiment:

```bash
# No spot VMs (aka no VM eviction)
inv makespan.run.granny --workload mpi-spot --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS}

# Spot VMs (aka VM eviction)
inv makespan.run.granny --workload mpi-spot --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS} --fault
```

During an experiment, you may monitor the state of the cluster (in a separete
shell) by using:

```bash
faasmctl monitor.planner --policy spot
```

Once you are done, you may delete the cluster:

```bash
faasmctl delete
```

## Delete the AKS cluster

Once you are done with the cluster, run:

```bash
inv cluster.delete
```

## Plot the results

Finally, you may plot the results wiht:

```bash
inv makespan.plot.spot
```
