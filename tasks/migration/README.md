# Migration Experiment

This experiment explores the benefits of migrating the execution of scientific
applications to benefit from dynamic changes in the compute environment.

First, provision the cluster:

```bash
(faasm-exp-pase) inv cluster.provision --vm Standard_D8_v5 --nodes 2 --name ${CLUSTER_NAME}
(faasm-exp-base) inv cluster.credentials --name ${CLUSTER_NAME}
```

Second, deploy Granny:

```bash
(faasm-exp-faabric) faasmctl deploy.k8s --workers 2
```

Second, upload the WASM files:

```bash
(faasm-exp-faabric) inv migration.wasm.upload
```

Third, run the experiments:

```bash
(faasm-exp-faabric) inv migration.run
```

Lastly, plot the results:

```bash
(faasm-exp-faabric) inv migration.plot
```

and clean up:

```bash
(faasm-exp-faabric) faasmctl delete
```

## Migration Oracle

As a sanity-check, and in order to evaluate the potential benefits of migrating,
we can run an oracle to see what is the impact of distribution in the execution
time of a simulation.
