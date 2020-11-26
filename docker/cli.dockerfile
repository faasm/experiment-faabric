ARG EXPERIMENT_VERSION
FROM faasm/experiment-base:${EXPERIMENT_VERSION}

# Install LAMMPS
WORKDIR /usr/local/code/lammps
RUN git clone --branch faasm https://github.com/faasm/lammps

# Build LAMMPS
RUN inv -r build.build
