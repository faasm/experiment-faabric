FROM faasm/openmpi:0.0.2

WORKDIR /code
RUN git clone https://github.com/faasm/experiment-mpi

WORKDIR /code/experiment-mpi

# TODO - remove, dev
RUN git checkout hoststats

RUN git submodule update --init

# Install Python deps
RUN pip3 install -r requirements.txt

# Compile to wasm
RUN inv kernels.build.wasm

# Compile natively
RUN inv kernels.build.native
