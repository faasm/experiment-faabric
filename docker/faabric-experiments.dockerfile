# Build the experiments' code
FROM faasm.azurecr.io/examples-build:0.2.5_0.2.5 as build

RUN rm -rf /code \
    && mkdir -p /code \
    && cd /code \
    # TODO: clone from main eventually
    && git clone -b new-wamr https://github.com/faasm/examples /code/faasm-examples \
    && cd /code/faasm-examples \
    && git submodule update --init -f cpp \
    && git submodule update --init -f python \
    && git submodule update --init -f examples/Kernels \
    && git submodule update --init -f examples/lammps \
    && git submodule update --init -f examples/lammps-migration \
    && git submodule update --init -f examples/LULESH \
    && ./bin/create_venv.sh \
    && source ./venv/bin/activate \
    && inv \
        kernels --native \
        kernels \
        lammps --native \
        lammps \
        lammps --migration --native \
        lammps --migration \
        lulesh --native \
        lulesh \
    && inv \
        func lammps chain \
        func mpi migrate

# Prepare the runtime to run the native experiments
FROM faasm.azurecr.io/openmpi:0.3.0

COPY --from=build --chown=mpirun:mpirun /code/faasm-examples /code/faasm-examples
COPY --from=build --chown=mpirun:mpirun /usr/local/faasm/wasm/lammps/main/function.wasm /code/faasm-examples/lammps.wasm
COPY --from=build --chown=mpirun:mpirun /usr/local/faasm/wasm/lammps/chain/function.wasm /code/faasm-examples/lammps_chain.wasm
COPY --from=build --chown=mpirun:mpirun /usr/local/faasm/wasm/mpi/migrate/function.wasm /code/faasm-examples/mpi_migrate.wasm

# Install OpenMP
ARG DEBIAN_FRONTEND=noninteractive
RUN apt update \
    && apt install -y libomp-13-dev
