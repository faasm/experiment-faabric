# Migration Experiment

This experiment explores the benefits of migrating the execution of scientific
applications to benefit from dynamic changes in the compute environment.

First, provision the cluster:

```bash
inv cluster.provision --vm Standard_D8_v5 --nodes 2 --name ${CLUSTER_NAME}
inv cluster.credentials --name ${CLUSTER_NAME}
```

## Granny

```bash
cd ~/faasm
source ./bin/workon.sh
inv k8s.deploy --workers 2
```
