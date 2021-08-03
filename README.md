# LAMMPS experiment

The Faasm fork of LAMMPS can be found [here](https://github.com/faasm/lammps),
with original source [here](https://lammps.sandia.gov/).

## Quick start

This project runs inside the container defined in this repo. To run it:

```bash
./bin/cli.sh
```

From inside, you can build and run the experiments with:

```bash
# Native
inv native

# Wasm
inv wasm
```

