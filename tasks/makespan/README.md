# Makespan Experiment

**IMPORTANT:** this experiment assumes that you have faasm checked-out under
`~/faasm`. It also assumes that the experiments repos are cloned as submodules:
`experiment-base/experiments/experiment-mpi`.

To run all the commands here included, first activate the virtual environment
in experiments base, `source ../../bin/workon.sh`.

## Metrics

* Provider Cost (PC): time integral of the number of idle cores
* User Cost (UC): average job execution time (total, or per user)
* Service Time (ST): average job service time (total, or per user)

## Generate the experiment trace

An experiment E is a set of jobs (or tasks), where each job is defined by: (i)
its arrival time, (ii) its size requirements, and (iii) the user it belongs
to.

In the future we will also differentiate if its an MPI or OpenMP job.

To generate a trace run:

```bash
inv makespan.trace.generate --num-tasks 10 --num-cores-per-vm 4 --num-users 2
```

## Deploy the experiment

```bash
export NUM_VMS=<NUM_VMS>
export NUM_CORES_PER_VM=<NUM_CORES_PER_VM>
export CTRS_PER_VM=<NUM_CONTAINERS_PER_VM>
```

### On `docker compose`

#### Native baselines

Run:

```bash
inv makespan.native.deploy --backend=[k8s,compose] --num-vms ${NUM_VMS} --ctrs-per-vm ${CTRS_PER_VM}
```

#### Granny

```bash
cd ~/faasm
source ./bin/workon.sh
OVERRIDE_CPU_COUNT=${NUM_CORES_PER_VM} inv cluster.start --workers ${NUM_NODES}
```

### On kubernetes

First, create the AKS cluster:

```bash
inv cluster.provision --vm Standard_D${NUM_CORES_PER_VM}_v5 --nodes ${NUM_VMS}
inv cluster.credentials
```

#### Native baselines

For the different native baselines, change the `--ctrs-per-vm` value between
1, 2, 4, and 8:

```bash
inv makespan.native.deploy --backend k8s --num-vms ${NUM_VMS} --ctrs-per-vm ${CTRS_PER_VM}
```

#### Granny

First, deploy Granny on the cluster:

```bash
cd ~/faasm
source ./bin/workon.sh
inv deploy.k8s --workers ${NUM_VMS}
```

Then, upload the necessary files and WASM:

```bash
cd ~/experiment-base/experiments/experiment-mpi
source ../../bin/workon.sh
inv makespan.wasm.upload
````

## Run the experiment

You can run a specific experiment specifying which baseline to run, on which
backend and an input trace with the following task. To run the experiments on
Granny, remember to pass the `--granny` flag at the end.

```bash
inv makespan.run --backend [k8s,compose] --num-vms ${NUM_VMS} --ctrs-per-vm <> --trace [trace_file_name.csv] [--granny]
```

You can also run all workloads at once for one backend:

```bash
inv makespan.run --backend [k8s,compose] --workload all --trace [trace_file_name.csv]
```

## Plot the results

```bash
inv makespan.plot --backend <> --num-vms <> --trace "trace_100_4_2.csv"
```
