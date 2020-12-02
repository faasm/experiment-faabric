#!/bin/bash

set -e

THIS_DIR=$(dirname $(readlink -f $0))
PROJ_ROOT=${THIS_DIR}/..

pushd ${PROJ_ROOT} > /dev/null

EXPERIMENTS_VERSION=$(cat VERSION)
CLI_IMAGE=faasm/experiment-lammps:${EXPERIMENTS_VERSION}

echo "Running LAMMPS Experiment CLI (${CLI_IMAGE})"

# Make sure the CLI is running already in the background (avoids creating a new
# container every time)
docker-compose \
    up \
    --no-recreate \
    -d \
    cli 

# Attach to the CLI container
docker-compose \
    exec \
    cli \
    /bin/bash

popd > /dev/null
