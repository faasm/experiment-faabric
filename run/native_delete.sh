#!/bin/bash

THIS_DIR=$(dirname $(readlink -f $0))
PROJ_ROOT=${THIS_DIR}/..

pushd ${PROJ_ROOT} >> /dev/null

# Delete the deployment
kubectl delete -f k8s/deployment.yml
kubectl delete -f k8s/namespace.yml

popd >> /dev/null
