# Build the experiments' code
FROM faasm.azurecr.io/examples-build:0.5.0_0.4.0 as build

RUN rm -rf /code \
    && mkdir -p /code \
    && cd /code \
    # TODO: back to main branch
    && git clone -b omp-elastic https://github.com/faasm/examples /code/faasm-examples \
    && cd /code/faasm-examples \
    # Checkout to a specific commit, to make sure we do not forget to update it
    # when changes occur upstream, and we do not accidentally cache old WASM
    # versions
    && git checkout af49d15e623db0d8404948d7e06f12bed92ad6ec \
    && git submodule update --init -f cpp \
    && git submodule update --init -f python \
    && git submodule update --init -f examples/Kernels \
    && git submodule update --init -f examples/Kernels-elastic \
    && git submodule update --init -f examples/lammps \
    && git submodule update --init -f examples/lammps-migration \
    && git submodule update --init -f examples/lammps-migration-net \
    && git submodule update --init -f examples/LULESH \
    && git submodule update --init -f examples/polybench \
    && ./bin/create_venv.sh \
    && source ./venv/bin/activate \
    && inv kernels --native \
    && inv kernels \
    # FIXME: for some reason, build only works if we create these directories
    # manually. Annoyingly, the problem can not be reproduced inside the
    # container image
    && mkdir -p /code/faasm-examples/examples/Kernels-elastic/build/native \
    && inv kernels --elastic --native --clean \
    && mkdir -p /code/faasm-examples/examples/Kernels-elastic/build/wasm \
    && inv kernels --elastic --clean \
    && inv lammps --native \
    && inv lammps \
    && inv lammps --migration --native \
    && inv lammps --migration \
    && inv lammps --migration-net --native \
    && inv lammps --migration-net \
    && inv lulesh --native \
    && inv lulesh \
    && inv polybench \
    && inv polybench --native \
    && inv func lammps chain \
    && inv func mpi migrate

# Prepare the runtime to run the native experiments
FROM faasm.azurecr.io/openmpi:0.5.0

COPY --from=build --chown=mpirun:mpirun /code/faasm-examples /code/faasm-examples
COPY --from=build --chown=mpirun:mpirun /usr/local/faasm/wasm/mpi/migrate/function.wasm /code/faasm-examples/mpi_migrate.wasm
COPY --from=build --chown=mpirun:mpirun /usr/local/faasm/wasm/polybench/ /code/faasm-examples/polybench/

# Install OpenMP
ARG DEBIAN_FRONTEND=noninteractive
RUN apt update \
    && apt install -y libomp-17-dev
