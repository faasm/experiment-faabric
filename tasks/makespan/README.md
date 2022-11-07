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

## Baselines

* Provider Cost Optimised (`pc-opt`):
* User Cost Optimised (`uc-opt`):
* Service Time Optimised (`st-opt`):

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

### On `docker compose`

Run:

```bash
inv makespan.native.deploy --num-nodes <> --local --baseline [uc-opt,pc-opt]
```

#### Native baselines

#### Granny

### On kubernetes

## Run the experiment

You can run an experiment specifying which baseline to run, on which backend
and an input trace with the following task:

```bash
inv makespan.run --backend [k8s,compose] --workload [uc-opt,pc-opt,st-opt,granny] --trace [trace_file_name.csv]
```

## Plots

### Number of idle cores over time

This experiment shows that Granny minimises the cost for the provider (by
minimising the number of idle cores) whilst providing:
  - Better performance than a system optimised to minimise the provider cost (`pc-opt`)
  - Comparable performance to a system optimised to maximise performance

In this experiment we measure the CDF of idle cores against a percentage of the
executed time:
  - X axis: percentage of executed time
  - Y axis: CDF of the number of idle cores

In the results, compared to `uc-opt` we want `granny`'s timeseries to have the
same length, yet lower number of idle cores.

