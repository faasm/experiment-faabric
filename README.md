# Faasm Experiments - LAMMPS

LAMMPS is a framweork for efficiently computing short-range molecular dynamics.
It is an MPI only project but can also be run in a OpenMP-MPI hybrid fashion.

The original source code can be found [here](https://lammps.sandia.gov/).
There's also a Faasm specific fork with the updated compilation toolchain
[here](https://github.com/faasm/lammps), change branch to `faasm`.

## Quick start

This tutorial assumes that this repository is cloned as a submodule of
[faasm/experiment-base](https://github.com/faasm/experiment-base).
Additionally, you need to activate the virtual environment in `experiment-base`.

Then, you can first build the experiment container:
```bash
./bin/build_container.sh
```

And run the experiments via:
```bash
./run/native.sh
./run/faasm.py
```

Both will populate result files in `./experiment-base/results/lammps`, where you
may also plot them.

## Experiment notes - Remove

### Achieving longer runs with LAMMPS:

+ Using the `controller` example, change the `run` command argument (last line)
and increase the number of timestep intervals by a factor of a 100. Still
communication bound.
+ Using the `HEAT` example (extracted from a paper) is way more compute bound.
However, it takes a _long_ time to run. To shorten it, we can do the inverse
step described before, and reduce the number of intervals. TODO: we'd need to
support 3-dim cartesian grids.

### Runing native locally without cluster

+ Set up the deployment using compose. Bear in mind that the total number of 
available hosts will be `NUM_WORKERS + 1`.
```bash
docker-compose up -d --scale worker=<NUM_WORKERS>
```

+ Then just generate the `hostfile` and run:
```bash
python3 ./run/docker_gen_hostfile.py
python3 ./run/docker_native.py
```

+ If you want to change any experiment parameters, look either into
`./run/docker_native.py` or `./run/all_native.py`.

