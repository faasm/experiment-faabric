ARG EXPERIMENT_VERSION
FROM faasm/experiment-lammps:${EXPERIMENT_VERSION}

WORKDIR /code/experiment-mpi

# TODO - remove before merging in
RUN git fetch origin
RUN git checkout makespan

RUN inv makespan.native.build
