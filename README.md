# LAMMPS experiment

The Faasm fork of LAMMPS can be found [here](https://github.com/faasm/lammps),
with original source [here](https://lammps.sandia.gov/).

This project runs inside the container defined in this repo. To run it:

```bash
./bin/cli.sh
```

## Running on Faasm

To upload the data you can run:

```bash
# Local
inv data.upload --local

# Remote
inv data.upload --host <faasm_upload_host>
```

You can build the code with:

```bash
inv wasm
```

and upload with:

```bash
# Local
inv wasm.upload --local

# Remote
inv wasm.upload --host <faasm_upload_host>
```

To run it:

```bash
inv run.faasm --host <faasm_invoke_host> --port <faasm_invoke_port>
```

## Running natively

The native experiment has to use a "proper" MPI deployment.

The scripts to do this should be run outside the container, with `kubectl`
available to access your K8s cluster.

To set up the MPI deployment:

```bash
./run/native_deploy.sh
```

To then execute the experiments

```bash
./run/native.sh
```
