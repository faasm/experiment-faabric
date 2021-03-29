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

