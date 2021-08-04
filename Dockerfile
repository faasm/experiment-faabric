FROM faasm/cpp-sysroot:0.0.26

# Download and install OpenMPI
WORKDIR /tmp
RUN wget https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-4.1.0.tar.bz2
RUN tar xf openmpi-4.1.0.tar.bz2
WORKDIR /tmp/openmpi-4.1.0
RUN ./configure --prefix=/usr/local
RUN make -j `nproc`
RUN make install

# The previous steps take a lot of time, so be careful not to invalidate the
# Docker cache

# -------------------------------
# NATIVE MPI SETUP
# -------------------------------

# Add an mpirun user
RUN adduser --disabled-password --gecos "" mpirun
RUN echo "mpirun ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set up SSH (for native MPI)
RUN apt install -y openssh-server
RUN mkdir /var/run/sshd
RUN echo 'root:mpirun' | chpasswd

COPY ./ssh/sshd_config /etc/ssh/sshd_config

# Generate a key to be used by all hosts
RUN ssh-keygen -b 2048 -t rsa -f /home/mpirun/.ssh/id_rsa -q -N ""

# Copy into authorized keys
WORKDIR /home/mpirun/.ssh
COPY ./ssh/id_rsa.mpi.pub authorized_keys

# Copy SSH config into place
COPY ssh/config /home/mpirun/.ssh/config

# Set up perms on SSH files
RUN chmod -R 600 /home/mpirun/.ssh*
RUN chmod 700 /home/mpirun/.ssh
RUN chmod 644 /home/mpirun/.ssh/id_rsa.pub
RUN chown -R mpirun:mpirun /home/mpirun/.ssh

# -------------------------------
# EXPERIMENT CODE SETUP
# -------------------------------

# Download code and build LAMMPS
WORKDIR /code
RUN git clone https://github.com/faasm/experiment-lammps
WORKDIR /code/experiment-lammps

# TODO - remove this, assume master
RUN git checkout updates-0308

RUN git submodule update --init

# Install Python deps
RUN pip3 install -r requirements.txt

# Cross-compile and build LAMMPS for Faasm
RUN inv wasm

# Build natively
RUN inv native

CMD /code/experiment-lammps/ssh/start_sshd.sh
