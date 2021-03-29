#!/bin/bash

THIS_DIR=$(dirname $(readlink -f $0))
PROJ_ROOT=${THIS_DIR}/..
BASE_DIR=${PROJ_ROOT}/../..
VERSION=$(< ${BASE_DIR}/VERSION)

pushd ${PROJ_ROOT} >> /dev/null

# Apply corresponding file
IMAGE_NAME=faasm/experiment-lammps:${VERSION} \
  envsubst < ${BASE_DIR}/aks/deployment.yaml |\
  kubectl apply -f -

# Wait for deployment to be ready
kubectl wait --for=condition=ready --timeout="-1s" pod -l run=faabric -n faabric

# Run experiments
EXPERIMENT="lammps_native_aks" RUN_SCRIPT=$(pwd)/run/all_native.py \
  ${BASE_DIR}/aks/run_mpi_benchmark.sh

# Delete the deployment afterwards
kubectl delete -f ${BASE_DIR}/aks/deployment.yaml

popd >> /dev/null

