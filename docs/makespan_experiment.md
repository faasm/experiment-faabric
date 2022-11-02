## Makespan Experiment for Granny

### Metrics

* Provider Cost (PC): time integral of the number of idle cores
* User Cost (UC):
* Service Time (ST):

### Experimental Setup

We fix:
* An experiment trace `E`.
* A total (maximum) number of VMs.
* A number of CPUs per VM (all VMs have the same size).

### Experiment Trace

An experiment E is a set of jobs (or tasks), where each job is defined by: (i)
its arrival time, (ii) its size requirements, and (iii) the user it belongs
to.

In the future we will also differentiate if its an MPI or OpenMP job.

### Native Baselines

* Provider Cost Optimised (`pc-opt`):
* User Cost Optimised (`uc-opt`):
* Service Time Optimised (`st-opt`):
