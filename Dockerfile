ARG EXPERIMENTS_VERSION
ARG FAASM_VERSION
FROM faasm/experiment-base:${EXPERIMENTS_VERSION} as experiments

# Install LAMMPS
WORKDIR /experiments
RUN git clone https://github.com/faasm/experiment-lammps
WORKDIR /experiments/experiment-lammps
RUN git submodule update --init

# Build natively
RUN ./build/lammps.py native --clean
# Cross-compile and build LAMMPS
#RUN ./build/lammps.py faasm --clean

# Copy compiled binary and sample data
# COPY /experiments/experiment-lammps/third-party/lammps/build/lmp \
#     /usr/local/code/faasm/wasm/lammps/main/function.wasm
COPY /experiments/experiment-lammps/third-party/lammps/examples \
    /data/lammps-examples
COPY /experiments/experiment-lammps/third-party/lammps/examples/controller/in.controller.wall \
    /data/in.controller

WORKDIR /usr/local/code/faasm
COPY ./faasm.ini /usr/local/code/faasm
CMD ["/bin/bash", "-l"]
