FROM faasm.azurecr.io/cpp-sysroot:0.4.0

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

# Note that the following two repos are useful reference for this Dockerfile:
# - https://github.com/everpeace/kube-openmpi/tree/master
# - https://github.com/zakiournani/Simple-MPI-cluster-on-Kubernetes

# Add an mpirun user
RUN adduser --disabled-password --gecos "" mpirun
RUN echo "mpirun ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set up SSH (for native MPI)
RUN apt update -y && apt install -y openssh-server
RUN mkdir /var/run/sshd
RUN echo 'root:mpirun' | chpasswd

COPY ./ssh/sshd_config /etc/ssh/sshd_config

# Generate a key to be used by all hosts
WORKDIR /home/mpirun/.ssh
RUN ssh-keygen -b 2048 -t rsa -f /home/mpirun/.ssh/id_rsa -q -N ""

# Copy into authorized keys
RUN cp id_rsa.pub authorized_keys

# Copy SSH config into place
COPY ssh/config config

# Set up perms on SSH files
WORKDIR /home/mpirun
RUN chmod -R 600 .ssh
RUN chmod 700 .ssh
RUN chmod 644 .ssh/id_rsa.pub
RUN chown -R mpirun:mpirun .ssh

# SSH
EXPOSE 22

# Configure entrypoint
COPY ssh/sshd_wrapper.sh /sshd_wrapper.sh
COPY ssh/start.sh /start.sh
ENTRYPOINT "/start.sh"
