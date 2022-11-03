## Makespan Experiment

**IMPORTANT:** this experiment assumes that you have faasm checked-out under
`~/faasm`.

### Metrics

* Provider Cost (PC): time integral of the number of idle cores
* User Cost (UC):
* Service Time (ST):

### Baselines

* Provider Cost Optimised (`pc-opt`):
* User Cost Optimised (`uc-opt`):
* Service Time Optimised (`st-opt`):

### Generate the experiment trace

An experiment E is a set of jobs (or tasks), where each job is defined by: (i)
its arrival time, (ii) its size requirements, and (iii) the user it belongs
to.

In the future we will also differentiate if its an MPI or OpenMP job.

To generate a trace run:

```bash
inv makespan.trace.generate --num-tasks 10 --num-cores-per-vm 4 --num-users 2
```

### Run the experiment

### Plots

#### Number of idle cores over time

This experiment shows that Granny minimises the cost for the provider (by
minimising the number of idle cores) whilst providing:
  - Better performance than a system optimised to minimise the provider cost (`pc-opt`)
  - Comparable performance to a system optimised to maximise performance

In this experiment we measure the number of idle cores over time:
  - X axis: time (in seconds)
  - Y axis: number of idle cores

In the results, compared to `uc-opt` we want `granny`'s timeseries to have the
same length, yet lower number of idle cores.

