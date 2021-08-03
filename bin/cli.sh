#!/bin/bash

set -e

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJ_ROOT=${THIS_DIR}/..

pushd ${PROJ_ROOT} > /dev/null

export VERSION=$(cat VERSION)

if [[ -z "$FAASM_LOCAL_DIR" ]]; then
    echo "You must set your local /usr/local/faasm dir through FAASM_LOCAL_DIR"
    exit 1
fi

if [[ -z "$LAMMPS_CLI_IMAGE" ]]; then
    export LAMMPS_CLI_IMAGE=faasm/experiment-lammps:${VERSION}
fi

INNER_SHELL=${SHELL:-"/bin/bash"}

# Make sure the CLI is running already in the background (avoids creating a new
# container every time)
docker-compose -f docker-compose.yml \
    up \
    --no-recreate \
    -d \
    cli

# Attach to the CLI container
docker-compose -f docker-compose.yml \
    exec \
    cli \
    ${INNER_SHELL}

popd > /dev/null
