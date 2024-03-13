# Faabric Experiments

This repo contains the experiments for the [Faabric paper](
https://arxiv.org/abs/2302.11358).

When following any instructions in this repository, it is recommended to
have two open terminals:
* One on the [`experiment-base`](https://github.com/faasm/experiment-base) repo
  with the virtual environment activated (`source ./bin/workon.sh`). From now
  onward, we will refer to this shell by its venv name: `faasm-exp-base`.
* One with this repo and the virtual environment activated
  (`source ./bin/workon.sh`). From now onward, we will refer to this shell by
  its venv name: `faasm-exp-faabric`.

The former is used to provision/deprovision K8s clusters on Azure (with AKS),
and also to access low-level monitoring tools (we recommend `k9s`).

The latter is used to deploy Faabric clusters, run the experiments, and plot
the results.

## Experiments in this repository

Microbenchmarks:
* [Polybench](./tasks/polybench/README.md) - experiment to measure the baseline overhead of using WebAssembly to execute the [PolyBench/C](https://web.cse.ohio-state.edu/~pouchet.2/software/polybench/) kernels.
* [Kernels (MPI)](./tasks/kernels/README.md) - microbenchmark of Faabric's MPI implementation using a subset of the [ParRes Kernels](https://github.com/ParRes/Kernels)
* Kernels (OpenMP) - TODO
* LULESH - TODO
* [LAMMPS](./tasks/lammps/README.md) - experiment using Faabric to run a one-off molecule simulation using [LAMMPS](https://www.lammps.org)
* [Migration](./tasks/migration/README.md) - microbenchmark showcasing the benefits of migrating an MPI application to improve locality.

Macrobenchmarks:
* [Makespan](./tasks/makespan/README.md) - experiment using Faabric to run a trace of scientific applications over a shared cluster of VMs. Comes in three flavours:
  - [MPI Migration for Locality] - TODO
  - [OpenMP Elastic Scaling to improve utilisation] - TODO
  - [MPI + OpenMP Migration to reduce VM working set] - TODO
