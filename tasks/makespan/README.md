# Makespan Experiment

First, deploy the VM cluster:

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 32
inv cluster.credentials
```

## Granny (MPI)

First, deploy the k8s cluster:

```bash
cd ${FAASM_SRC_DIR}
WASM_VM=wamr inv k8s.deploy --workers=4
```

# Old instructions, remove

## Generate the experiment trace

An experiment E is a set of jobs (or tasks), where each job is defined by: (i)
its arrival time, (ii) its size requirements, and (iii) the user it belongs
to.

To generate a trace run:

```bash
inv makespan.trace.generate --workload [omp,mpi,mix] --num-tasks <> --num-cores-per-vm <>
```

## Deploy the experiment

### On `docker compose`

#### Native baselines

As previously described, the deployment scripts default to `k8s` and 32 VMs
with 8 cores per VM, so if you want to run on `compose` with smaller values
you will have to run:

```bash
inv makespan.native.deploy --backend=compose --num-vms <> --num-cores-per-vm  <> --ctrs-per-vm <>
```

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
