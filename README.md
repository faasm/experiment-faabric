# LAMMPS experiment

The Faasm fork of LAMMPS can be found [here](https://github.com/faasm/lammps),
with original source [here](https://lammps.sandia.gov/).

This project runs inside the container defined in this repo. To run it:

```bash
./bin/cli.sh
```

## Data

To upload the data you can run:

```bash
# Local
inv data.upload --local

# Remote
inv data.upload --host <faasm_upload_host>
```

## Building code

You can build the code with:

```bash
# Native
inv native

# Wasm
inv wasm
```

To upload the wasm code to Faasm:

```bash
# Local
inv wasm.upload --local

# Remote
inv wasm.upload --host <faasm_upload_host>
```
