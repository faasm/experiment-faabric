ARG EXPERIMENTS_VERSION
FROM faasm/experiment-base:${EXPERIMENTS_VERSION} as experiments

# Install LAMMPS
WORKDIR /code
RUN git clone -b resurrect https://github.com/faasm/experiment-lammps
WORKDIR /code/experiment-lammps
RUN git submodule update --init

# Build natively
RUN python3 ./build/lammps.py native --clean
# Cross-compile and build LAMMPS
# RUN python3 ./build/lammps.py faasm --clean

# Copy compiled binary and sample data
# COPY /experiments/experiment-lammps/third-party/lammps/build/lmp \
#     /usr/local/code/faasm/wasm/lammps/main/function.wasm
WORKDIR /data
RUN cp /code/experiment-lammps/third-party/lammps/examples/controller/in.controller.wall \
    /data/in.controller

WORKDIR /usr/local/code/faasm
COPY ./faasm.ini /usr/local/code/faasm
CMD ["/bin/bash", "-l"]
