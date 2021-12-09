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
source ../../bin/workon.sh

inv -l
```

## Running LAMMPS on Faasm

The code must be built within the LAMMPS container:

```bash
git submodule update --init

./bin/cli.sh lammps

inv lammps.wasm
```

The code can then be uploaded from _outside_ the container:

```bash
# Set up local env
source ../../bin/workon.sh

inv lammps.data.upload

inv lammps.wasm.upload
```

The experiment can then be run with:

```bash
inv lammps.run.faasm
```

## Running Kernels on Faasm

Building the code must be done from within the kernels experiment container:

```bash
git submodule update --init

./bin/cli.sh kernels

inv kernels.build.wasm
```

Then upload and run outside the container:

```bash
source ../../bin/workon.sh

inv kernels.build.upload

inv kernels.run.faasm
```

## Running LAMMPS on OpenMPI

To deploy:

```bash
source ../../bin/workon.sh

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
source ../../bin/workon.sh

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

## Plotting the Execution Graph

To plot any part of the execution graph we need to run the application with
the graph flag set:

```bash
inv lammps.run.faasm --bench compute --nprocs 4 --graph
```

At the very beginning, the application will log out its call id, which we will
need to plot the execution graph using:

```bash
inv lammps.run.exec-graph <call-id>
```

You can alternatively plot the same graph with just one type of message, where
the message type is an integer as defined [here](https://github.com/faasm/faabric/blob/4d2c310c02da43d4b81156fea717856d8443eba4/src/proto/faabric.proto#L66-L76).
By default, all message types will be plotted.

```bash
inv lammps.run.exec-graph <call-id> --msg-type <msg-type>
```

Lastly, you can also plot the breakdown of cross-host messages divided by
message type, and sender rank.

```bash
inv lammps.run.exec-graph <call-id> --xhost
```

## Rebuilding containers

To rebuild the containers:

```bash
source ../../bin/workon.sh

# OpenMPI
inv openmpi.build

# LAMMPS
inv lammps.container

# Kernes
inv kernels.container
```

