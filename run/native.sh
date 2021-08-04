#!/bin/bash

THIS_DIR=$(dirname $(readlink -f $0))
PROJ_ROOT=${THIS_DIR}/..

CLUSTER_SIZE=5
MPI_MAX_PROC=2

pushd ${PROJ_ROOT} >> /dev/null

# Get the master
MPI_MASTER=$(kubectl -n ${NAMESPACE} get pods -l run=faabric | awk 'NR==2 {print $1}')
echo "Chosen as master node w/ name: ${MPI_MASTER}"

# Run the benchmark
kubectl -n mpi-native \
    exec -it \
    ${MPI_MASTER} -- bash -c "su mpirun -c '/home/mpirun/all.py'"

# Grep the results
mkdir -p results
kubectl cp mpi-native/${MPI_MASTER}:/home/mpirun/results.dat \
    ./results/lammps_native.dat

# Delete results on the host
kubectl -n ${NAMESPACE} exec -it \
    ${MPI_MASTER} -- bash -c "rm /home/mpirun/results.dat"

popd >> /dev/null

