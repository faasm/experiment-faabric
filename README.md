# Faasm Experiments - LAMMPS

LAMMPS is a framweork for efficiently computing short-range molecular dynamics.
It is an MPI only project but can also be run in a OpenMP-MPI hybrid fashion.

The original source code can be found [here](https://lammps.sandia.gov/).
There's also a Faasm specific fork with the updated compilation toolchain
[here](https://github.com/faasm/lammps), change branch to `faasm`.

## Run the experiments

The whole build process is containerized, and that's the only way to interact
with the deployment. In particular, the Docker build cross-compiles LAMMPS to 
WebAssembly, and prepares the necessary dependencies. The experiments run
against Faasm deployed as a service. 

To deploy the necessary services and run an example workload you can do:
```bash
# This sets up the necessary Faasm architecture
docker-compose up -d

# Launch the cli container
./bin/cli.sh

# Code generation step (may take a while)
(faasm) inv upload lammps main
# Upload the sample data file and run the binary
(faasm) inv state.shared-file /data/in.controller /lammps-data/in.controller
(faasm) lammps_pool_runner
```
