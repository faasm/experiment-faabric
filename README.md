# MPI Experiments

This repo contains two MPI-based experiments, using
[LAMMPS](https://lammps.sandia.gov/) and the
[ParRes Kernels](https://github.com/ParRes/Kernels).

The Faasm fork of LAMMPS can be found [here](https://github.com/faasm/lammps),
and of ParRes Kernels [here](https://github.com/faasm/Kernels).

This project runs inside one of two containers defined in this repo:

```bash
# LAMMPS
./bin/cli.sh lammps

# Kernels
./bin/cli.sh kernels
```

To rebuild the containers:

```bash
# OpenMPI
inv openmpi.container

# LAMMPS
inv lammps.container

# Kernes
inv kernels.container
```

## Running LAMMPS on Faasm

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

To run it:

```bash
inv lammps.run.faasm --host <faasm_invoke_host> --port <faasm_invoke_port>
```

## Running Kernels on Faasm

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

To run it:

```bash
inv kernels.run.faasm --host <faasm_invoke_host> --port <faasm_invoke_port>
```

## Running natively

Both native experiments use OpenMPI in a K8s cluster. To deploy this we can run:

```bash
# Local
inv openmpi.deploy --local

# Remote
inv openmpi.deploy
```

Check the deployment with `kubectl`:

```bash
kubectl -n faasm-mpi-native get deployments
```

Once ready, we can template the MPI host file on all the containers:

```bash
inv openmpi.hostfile
```

We can then execute the experiments natively with:

```bash
# LAMMPS
inv lammps.run.native

# Kernels
inv kernels.run.native
```
