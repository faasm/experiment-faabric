ARG EXPERIMENT_VERSION
FROM faasm/experiment-lammps:${EXPERIMENT_VERSION}

# Fetch sufficiently new CPP version
WORKDIR /code/cpp
RUN git fetch origin
RUN git checkout v0.1.6

WORKDIR /code/experiment-mpi

# TODO - remove before merging in
RUN git fetch origin
RUN git checkout makespan

# TODO - do we even need this here?
RUN inv makespan.native.build
