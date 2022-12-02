#!/bin/bash

set -e

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]:-${(%):-%x}}" )" >/dev/null 2>&1 && pwd )"
PROJ_ROOT="${THIS_DIR}/.."

echo "Setting up venv at ${PROJ_ROOT}/venv"
python3.10 -m venv ${PROJ_ROOT}/venv
source ${PROJ_ROOT}/venv/bin/activate

pip3 install -U pip
pip3 install -U setuptools
pip3 install -r requirements.txt
