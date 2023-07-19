# Makespan Experiment

First, from the `experiment-base` shell, deploy the VM cluster:

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 32
inv cluster.credentials
```

## Native

First, deploy the native `k8s` cluster:

```bash
inv makespan.native.deploy
```

Now, you can run the different baselines:

```bash
inv makespan.run.native-batch --workload [mpi,omp]
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

# Old instructions, remove

## Deploy the experiment

### On `docker compose`

#### Granny

```bash
cd ~/faasm
source ./bin/workon.sh
OVERRIDE_CPU_COUNT=${NUM_CORES_PER_VM} inv cluster.start --workers ${NUM_NODES}
```

### On kubernetes

First, create the AKS cluster.

**Important:** you need to run this command from `experiment-base` not
`experiment-base/experiments/mpi`. So, exceptionally, `cd ../..`, run it and
then `cd -`.

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 32
inv cluster.credentials
```

#### Native baselines

For the different native baselines, change the `--ctrs-per-vm` value between
1, 2, 4, and 8:

```bash
inv makespan.native.deploy --ctrs-per-vm ${CTRS_PER_VM}
```

To change to a different `CTRS_PER_VM` value, first delete the deployment and
then run it again:

```
inv makespan.native.delete --ctrs-per-vm ${OLD_CTRS_PER_VM}
inv makespan.native.deploy --ctrs-per-vm ${NEW_CTRS_PER_VM}
```

You need to wait a non-deterministic amount of time for all pods in the old
deployment to disappear (as they linger in `Terminating` state for a while).
The best way to be sure when the cluster is ready to run is to inspect the
deployment using `k9s`. Alternatively, if you try to run the experiment before
the deployment is ready, the script will return an error.

#### Granny

First, deploy Granny on the cluster:

```bash
cd ~/faasm
source ./bin/workon.sh
inv k8s.deploy --workers 32
```

Then, upload the necessary files and WASM. This will copy the pre-compiled
binaries from a docker image available on DockerHub (`faasm/experiment-makespan:0.2.0`).
Make sure you have the latest version of the image. The script will pull the
image if it is not there, but to be extra sure run `docker pull faasm/experiment-makespan:0.2.0`.

```bash
inv makespan.wasm.upload
````

## Run the experiment

We run either `granny` or `native` with different `ctrs-per-vm` parameters. In
addition, we can either run an `mpi` or an `omp` trace.

We assume the defaults to be:

```bash
backend="k8s"
num-tasks=100
num-vms=32
num-cores-per-vm=8
```

To run `granny` do:

```bash
inv makespan.run.granny --workload=[mpi,omp,all]
```

To run one `native` baseline do:

```bash
inv makespan.run.native --workload=[mpi,omp,all] --ctrs-per-vm=[1,2,4,8]
```

## Plot the results

To plot the results, just run:

```bash
inv makespan.plot
```

## Remove the cluster

It is very important that you remove the AKS k8s cluster once you are not using
it anymore. To do so run:

```bash
cd ~/experiment-base
inv cluster.delete
```
