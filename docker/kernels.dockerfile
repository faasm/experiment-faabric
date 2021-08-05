FROM faasm/openmpi:0.1.0

# Clone the repo
WORKDIR /code
RUN git clone https://github.com/faasm/experiment-kernels
RUN git submodule update --init

WORKDIR /code/experiment-kernels

# Install Python deps
RUN pip3 install -r requirements.txt

# Compile to wasm
RUN inv wasm

# Compile natively
RUN inv native
