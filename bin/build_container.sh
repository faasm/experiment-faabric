#!/bin/bash

set -e

THIS_DIR=$(dirname $(readlink -f $0))
PROJ_ROOT=${THIS_DIR}/..
BASE_DIR=${PROJ_ROOT}/../..

IMAGE_NAME="experiment-lammps"
VERSION="$(< ${BASE_DIR}/VERSION)"
FAASM_VERSION="$(< ${BASE_DIR}/faasm/VERSION)"

pushd ${PROJ_ROOT} >> /dev/null

export DOCKER_BUILDKIT=1

# Docker args
NO_CACHE=$1

# Create faasm.ini file for up-to-date knative deployment
${BASE_DIR}/faasm/bin/knative_route.sh | tail -7 > faasm.ini

docker build \
    ${NO_CACHE} \
    -t faasm/${IMAGE_NAME}:${VERSION} \
    -f ${PROJ_ROOT}/Dockerfile \
    --build-arg EXPERIMENTS_VERSION=${VERSION} \
    ${PROJ_ROOT}

# Remove faasm.ini file
rm faasm.ini

# Upload lammps function + data
docker run --rm \
    faasm/experiment-lammps:${VERSION} \
    inv -r faasmcli/faasmcli upload lammps main \
    /code/experiment-lammps/third-party/lammps/install/bin/lmp
docker run --rm \
    faasm/experiment-lammps:${VERSION} \
    inv -r faasmcli/faasmcli state.shared-file \
    /data/in.controller /lammps-data/in.controller

# Push the image to docker hub if required
if [ "${BASH_ARGV[0]}" == "--push" ]; then
    docker push faasm/${IMAGE_NAME}:${VERSION}
fi

popd >> /dev/null

