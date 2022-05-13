ARG EXPERIMENT_VERSION
FROM faasm/experiment-lammps:${EXPERIMENT_VERSION}

WORKDIR /code/experiment-mpi

# TODO - remove before merging in
RUN git fetch origin
RUN git checkout makespan

# TODO - do we even need this here?
RUN inv makespan.native.build
