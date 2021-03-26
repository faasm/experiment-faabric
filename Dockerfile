ARG EXPERIMENTS_VERSION

# We pin to a specific sysroot release
FROM faasm/cpp-sysroot:0.0.22 as build-step

# Download code and build LAMMPS
WORKDIR /code
RUN git clone -b resurrect https://github.com/faasm/experiment-lammps
WORKDIR /code/experiment-lammps
RUN git submodule update --init

# Build natively
RUN python3 ./build/lammps.py native --clean
# Cross-compile and build LAMMPS
RUN python3 ./build/lammps.py faasm --clean

FROM faasm/experiment-base:${EXPERIMENTS_VERSION} as experiments

# Copy experiment code and built artifacts
COPY --from=build-step /code/experiment-lammps /code/experiment-lammps
# Shortcut for input data
WORKDIR /data
RUN cp /code/experiment-lammps/third-party/lammps/examples/controller/in.controller.wall \
    /data/in.controller

# Copy faasm.ini file to interact w/ k8s
WORKDIR /usr/local/code/faasm
COPY ./faasm.ini /usr/local/code/faasm
CMD ["/bin/bash", "-l"]
