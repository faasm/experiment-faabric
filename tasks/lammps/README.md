# LAMMPS Experiment

This experiment is a single execution of the LAMMPS simulation stress tested
as part of the array experiment.

## Start AKS cluster

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 2
inv cluster.credentials
```

## Granny

Deploy the cluster, and point an env. var to the cluster deployment file:

```bash
faasmctl deploy.k8s --workers=2
export FAASM_INI_FILE=./faasm.ini
```

Upload the WASM file:

```bash
inv lammps.wasm.upload
```

To remove the cluster, run:

```bash
faasmctl delete
```

## Native

Deploy the cluster:

```bash
inv lammps.native.deploy
```

And run:

```bash
inv lammps.run.native
```

# Plot

TODO:

## Clean-Up

Remember to delete the cluster:

```bash
inv cluster.delete
```
