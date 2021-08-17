# MPI Experiments

This repo contains two MPI-based experiments, using
[LAMMPS](https://lammps.sandia.gov/) and the
[ParRes Kernels](https://github.com/ParRes/Kernels).

The Faasm fork of LAMMPS can be found [here](https://github.com/faasm/lammps),
and of ParRes Kernels [here](https://github.com/faasm/Kernels).

Note, this repo should be checked out as part of the Faasm/ Faabric experiment
set-up covered in the [`experiment-base`
repo](https://github.com/faasm/experiment-base).

To check things are working:

```bash
../../bin/workon.sh

inv -l
```

## Running LAMMPS on Faasm

Building the code and uploading the data must be done from within the LAMMPS
experiment container:

```bash
./bin/cli.sh lammps
```

To upload the data you can run:

```bash
# Local
inv lammps.data.upload --local

# Remote
inv lammps.data.upload --host <faasm_upload_host>
```

You can build the code with:

```bash
inv lammps.wasm
```

and upload with:

```bash
# Local
inv lammps.wasm.upload --local

# Remote
inv lammps.wasm.upload --host <faasm_upload_host>
```

The experiment must be run _outside_ the container:

```bash
# Set up local env
../../bin/workon.sh

# Run the experiment
inv lammps.run.faasm --host <faasm_invoke_host> --port <faasm_invoke_port>
```

## Running Kernels on Faasm

Building the code must be done from within the kernels experiment container:

```bash
./bin/cli.sh kernels
```

You can build the code with:

```basn
inv kernels.build.wasm
```

and upload with:

```bash
# Local
inv kernels.build.upload --local

# Remote
inv kernels.build.upload --host <faasm_upload_host>
```

The experiment must be run _outside_ the container:

```bash
../../bin/workon.sh

inv kernels.run.faasm --host <faasm_invoke_host> --port <faasm_invoke_port>
```

## Running LAMMPS on OpenMPI

To deploy:

```bash
../../bin/workon.sh

inv lammps.native.deploy
```

Wait for all the containers to become ready. Check with:

```bash
kubectl -n openmpi-lammps get deployments --watch
```

Once ready, we can template the MPI host file on all the containers:

```bash
inv lammps.native.hostfile
```

Execute with:

```bash
inv lammps.run.native
```

Once finished, you can remove the OpenMPI deployment with:

```bash
inv lammps.native.delete
```

## Running Kernels on OpenMPI

To deploy:

```bash
../../bin/workon.sh

inv kernels.native.deploy
```

Wait for all the containers to become ready. Check with:

```bash
kubectl -n openmpi-kernels get deployments --watch
```

Once ready, we can template the MPI host file on all the containers:

```bash
inv kernels.native.hostfile
```

Execute with:

```bash
inv kernels.run.native
```

Once finished, you can remove the OpenMPI deployment with:

```bash
inv kernels.native.delete
```

## Rebuilding containers

To rebuild the containers:

```bash
../../bin/workon.sh

# OpenMPI
inv openmpi.container

# LAMMPS
inv lammps.container

# Kernes
inv kernels.container
```
