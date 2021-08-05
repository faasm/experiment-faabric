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

The native experiment has to use OpenMPI in the K8s cluster. To deploy this we
can run:

```bash
# Local
inv mpi.deploy --local

# Remote
inv mpi.deploy
```

Check the deployment with `kubectl`:

```bash
kubectl -n faasm-mpi-native get deployments
```

Once ready, we can template the MPI host file on all the containers:

```bash
inv mpi.hostfile
```

We can then execute the experiment natively with:

```bash
inv run.native
```
