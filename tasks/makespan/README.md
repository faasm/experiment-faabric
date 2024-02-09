# Makespan Experiment

First, from the `faasm-exp-base` shell, deploy the VM cluster:

```bash
(faasm-exp-base) inv cluster.provision --vm Standard_D8_v5 --nodes 32
(faasm-exp-base) inv cluster.credentials
```

## Native

First, deploy the native `k8s` cluster:

```bash
(faasm-exp-base) inv makespan.native.deploy --num-vms 32
```

Now, you can run the different baselines:

```bash
(faasm-exp-base) inv makespan.run.native-batch --workload mpi-migrate --num-vms 32 --num-tasks 100
(faasm-exp-base) inv makespan.run.native-slurm --workload mpi-migrate --num-vms 32 --num-tasks 100
```

Lastly, remove the native `k8s` cluster:

```bash
inv makespan.native.delete
```

## Granny (MPI)

First, deploy the k8s cluster:

```bash
# Optioanlly set the following env. variables
faasmctl deploy.k8s --workers=32
```

Second, upload the corresponding WASM files:

```bash
(faasm-exp-faabric) inv makespan.wasm.upload
```

Third, run the experiment:

```bash
# TODO: will probably ditch --workload=mpi
# (faasm-exp-faabric) inv makespan.run.granny --workload mpi
# Set the --migrate flag to enable migrating Granules at runtime
# TODO: rename the workload to `mpi`
(faasm-exp-faabric) inv makespan.run.granny --num-vms 32 --num-tasks 100 --workload mpi-migrate [--migrate]
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
inv motivation.plot
```

## Syntax

### Workload

A workload is the type of job that we are executing. It can either be `mpi`,
or `omp`.

### Experiment trace

An experiment E is a set of jobs (or tasks), where each job is defined by: (i)
its arrival time, (ii) its size requirements, and (iii) the user it belongs
to.

To generate a trace run:

```bash
inv makespan.trace.generate --workload [omp,mpi,mix] --num-tasks <> --num-cores-per-vm <>
```

### Baseline

A baseline is one of the systems that we evaluate in this experiment. We
currently support three different baselines: `granny`, `batch`, and `slurm`.
- `granny`: is our system
- `batch`: is native OpenMPI where jobs are scheduled at VM granularity
- `slurm` is native OpenMPI where jobs are shceduled at process granularity
