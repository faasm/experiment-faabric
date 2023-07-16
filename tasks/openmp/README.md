# OpenMP MicroBenchmark

This experiment studies the baseline overhead of executing OpenMP applications
using Granules instead of threads.

## Native baseline

To deploy, run:

```bash
inv openmp.native.deploy
```

Run with:

```bash
inv openmp.run.native
```

And delete with:

```bash
inv openmp.native.delete
```

## Granny

First, deploy the cluster:

```bash
cd ${FAASM_SRC}
inv k8s.deploy --workers=1
```

Second, upload the WASM files:

```bash
inv openmp.wasm.upload
```

Lastly, run the experiments:

```bash
inv openmp.run.granny
```
