#!/bin/bash

THIS_DIR=$(dirname $(readlink -f $0))
PROJ_ROOT=${THIS_DIR}/..

MPI_MAX_PROC=2

pushd ${PROJ_ROOT} >> /dev/null

# Do K8s deployment
kubectl apply -f k8s/deployment.yaml

# Wait for deployment to be ready
kubectl wait --for=condition=ready \
    --timeout="-10s" \
    pod -l run=mpi-native \
    -n mpi-native

# Generate the hostfile
kubectl get pods -n mpi-native -l run=faabric -o wide \
    | awk -v slots=${MPI_MAX_PROC} 'NR>1 {print $6" slots=" slots}' > hostfile

echo "Generated host file: "
cat hostfile

# SCP it to the first host
MPI_MASTER=$(kubectl -n mpi-native get pods -l run=mpi-native | awk 'NR==2 {print $1}')
echo "Chosen as master node w/ name: ${MPI_MASTER}"
kubectl cp hostfile mpi-native/${MPI_MASTER}:/home/mpirun/hostfile

# Copy the script over
kubectl cp run/all_native.py mpi-native/${MPI_MASTER}:/home/mpirun/all.py

popd >> /dev/null

