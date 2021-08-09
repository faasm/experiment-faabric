# MPI Experiments

This repo contains two MPI-based experiments, using
[LAMMPS](https://lammps.sandia.gov/) and the
[ParRes Kernels](https://github.com/ParRes/Kernels).

The Faasm fork of LAMMPS can be found [here](https://github.com/faasm/lammps),
and of ParRes Kernels [here](https://github.com/faasm/Kernels).

For general info on running these experiments (e.g. setting up the cluster),
see the [`experiment-base` repo](https://github.com/faasm/experiment-base).

```bash
# Kernels
./bin/cli.sh kernels
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

The experiment must be run _outside_ the container using the `experiment-base`
virtual environment:

```bash
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

The experiment must be run _outside_ the container using the `experiment-base`
virtual environment:

```bash
inv kernels.run.faasm --host <faasm_invoke_host> --port <faasm_invoke_port>
```

## Running natively

Both native experiments use OpenMPI in a K8s cluster. To deploy this we can run
the following using the `experiment-base` environment:

```bash
# Local
inv openmpi.deploy --local

# Remote
inv openmpi.deploy
```

Wait for all the containers to become ready. Check with:

```bash
kubectl -n faasm-openmpi get deployments --watch
```

If there are any issues, check logs with:

```bash
kubectl -n faasm-openmpi get pods
kubectl -n faasm-openmpi describe deployment/<deployment_name>
```

Once ready, we can template the MPI host file on all the containers:

```bash
inv openmpi.hostfile
```

Execute with:

```bash
# LAMMPS
inv lammps.run.native

# Kernels
inv kernels.run.native
```

Once finished, you can remove the OpenMPI deployment with:

```bash
inv openmpi.delete
```

## Rebuilding containers

To rebuild the containers:

```bash
# OpenMPI
inv openmpi.container

# LAMMPS
inv lammps.container

# Kernes
inv kernels.container
```
