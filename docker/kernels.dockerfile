FROM faasm/openmpi:0.0.1

# Clone the repo
WORKDIR /code
RUN git clone https://github.com/faasm/experiment-mpi
RUN git submodule update --init

WORKDIR /code/experiment-mpi

# TODO - remove once done
RUN git checkout merge-mpi

# Install Python deps
RUN pip3 install -r requirements.txt

# Compile to wasm
RUN inv kernels.wasm

# Compile natively
RUN inv kernels.native
