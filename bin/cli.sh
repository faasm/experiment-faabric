#!/bin/bash

set -e

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJ_ROOT=${THIS_DIR}/..

pushd ${PROJ_ROOT} > /dev/null

export VERSION=$(cat VERSION)

if [[ -z "$LAMMPS_CLI_IMAGE" ]]; then
    export LAMMPS_CLI_IMAGE=faasm/experiment-lammps:${VERSION}
fi

if [[ -z "$KERNELS_CLI_IMAGE" ]]; then
    export KERNELS_CLI_IMAGE=faasm/experiment-kernels:${VERSION}
fi

if [[ -z "$1" ]]; then
    echo "Must specify which CLI"
    exit 1

elif [[ "$1" == "lammps" ]]; then
    CLI_CONTAINER="lammps-cli"
    echo "LAMMPS CLI (${LAMMPS_CLI_IMAGE})"

elif [[ "$1" == "kernels" ]]; then
    CLI_CONTAINER="kernels-cli"
    echo "Kernels CLI (${KERNELS_CLI_IMAGE})"

else
    echo "Unrecognised CLI. Must be lammps or kernels"
    exit 1
fi

export INNER_SHELL=${SHELL:-"/bin/bash"}

# Make sure the CLI is running already in the background (avoids creating a new
# container every time)
docker-compose \
    up \
    --no-recreate \
    -d \
    ${CLI_CONTAINER}

# Attach to the CLI container
docker-compose \
    exec \
    ${CLI_CONTAINER} \
    ${INNER_SHELL}

popd > /dev/null
