ARG EXPERIMENTS_VERSION
FROM faasm/experiment-base:${EXPERIMENTS_VERSION}

# Install LAMMPS
WORKDIR /experiments
RUN git clone https://github.com/faasm/experiment-lammps
WORKDIR /experiments/experiment-lammps
RUN git clone --branch faasm https://github.com/faasm/lammps

# Build LAMMPS
# RUN inv -r build.build
