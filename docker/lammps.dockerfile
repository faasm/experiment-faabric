FROM faasm/openmpi:0.1.2

WORKDIR /code
RUN git clone https://github.com/faasm/experiment-mpi

WORKDIR /code/experiment-mpi

RUN git submodule update --init

# Install Python deps
RUN pip3 install -r requirements.txt

# Install curl for hoststats
RUN apt update
RUN apt install -y curl

# Cross-compile and build LAMMPS for Faasm
RUN inv lammps.wasm

# Build natively
RUN inv lammps.native

# hoststats port
EXPOSE 5000
