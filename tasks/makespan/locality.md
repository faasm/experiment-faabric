# Makespan Experiment (SPOT VM version)

In this experiment we study the benefits of using Granules to improve locality
of execution while maintaining high cluster utilisation.

For each experiment run, we increase the cluster size (in terms of number of
VMs) and the number of jobs in the tasks, proportionally.

Re-run the following instructions with the following values:

```bash
NUM_VMS=8,16,24,32
NUM_TASKS=50,100,150,200
```

## Deploy the cluster

First, to deploy the cluster, run:

```bash
export NUM_VMS=
export NUM_TASKS=

inv cluster.provision --vm Standard_D8_v5 --nodes ${NUM_VMS} + 1
inv cluster.credentials
```

## Native (OpenMPI)

First, deploy the native `k8s` cluster:

```bash
inv makespan.native.deploy --num-vms ${NUM_VMS}
```

Now, you can run the different OpenMPI baselines:

```bash
inv makespan.run.native-batch --workload mpi-migrate --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS}
inv makespan.run.native-slurm --workload mpi-migrate --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS}
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
# Granny with migration disabled as another baseline
inv makespan.run.granny --workload mpi-migrate --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS}

# Granny with migration enabled (aka Granny)
inv makespan.run.granny --workload mpi-migrate --num-vms ${NUM_VMS} --num-tasks ${NUM_TASKS} --migrate
```

During an experiment, you may monitor the state of the cluster (in a separete
shell) by using:

```bash
faasmctl monitor.planner
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

then you may move to the next (cluster size, batch size) pair.

## Plot the results

Finally, you may plot the results wiht:

```bash
inv makespan.plot.locality
```
