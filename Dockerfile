FROM faasm/cpp-sysroot:0.0.26

# Download and install OpenMPI
WORKDIR /tmp
RUN wget https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-4.1.0.tar.bz2
RUN tar xf openmpi-4.1.0.tar.bz2
WORKDIR /tmp/openmpi-4.1.0
RUN ./configure --prefix=/usr/local
RUN make -j `nproc`
RUN make install
# The previous steps take a lot of time, so don't move these lines and beneffit
# from Docker's incremental build

# Add an mpirun user
ENV USER mpirun
RUN adduser --disabled-password --gecos "" ${USER} && \
    echo "${USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
RUN apt update
# Dev tools delete eventually
RUN apt install -y gdb vim

# Set up SSH
RUN apt update && apt upgrade -y
RUN apt install -y openssh-server
RUN mkdir /var/run/sshd
RUN echo 'root:${USER}' | chpasswd
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

# User SSH config
ENV HOME /home/${USER}
WORKDIR ${HOME}/.ssh
COPY ./ssh/config config
COPY ./ssh/id_rsa.mpi id_rsa
COPY ./ssh/id_rsa.mpi.pub id_rsa.pub
COPY ./ssh/id_rsa.mpi.pub authorized_keys
RUN ssh-keygen -A
RUN chmod -R 600 ${HOME}/.ssh* && \
    chmod 700 ${HOME}/.ssh && \
    chmod 644 ${HOME}/.ssh/id_rsa.pub && \
    chmod 664 ${HOME}/.ssh/config && \
    chown -R ${USER}:${USER} ${HOME}/.ssh

# TODO - can we get rid of this?
# Set up experiment base code and plotting tools
# RUN apt-get update
# RUN apt-get install -y \
    #     python3-dev \
    #     python3-pip \
    #     python3-venv
#
# # Python set-up
# WORKDIR /experiments
# RUN git clone https://github.com/faasm/experiments experiment-base
# WORKDIR /experiments/experiment-base
# RUN pip3 install -r requirements.txt

# Start the SSH server for reachability
# WORKDIR ${HOME}
# CMD ["/usr/sbin/sshd", "-D"]

# Download code and build LAMMPS
WORKDIR /code
RUN git clone https://github.com/faasm/experiment-lammps
WORKDIR /code/experiment-lammps
RUN git submodule update --init

# Cross-compile and build LAMMPS for Faasm
RUN python3 ./build/lammps.py faasm --clean

# Build natively
RUN python3 ./build/lammps.py native --clean

# Shortcut for input data
WORKDIR /data
RUN cp /code/experiment-lammps/third-party/lammps/examples/controller/in.controller.wall \
    /data/in.controller

# Copy faasm.ini file to interact w/ k8s
WORKDIR /usr/local/code/faasm
COPY ./faasm.ini /usr/local/code/faasm
CMD ["/usr/sbin/sshd", "-D"]
