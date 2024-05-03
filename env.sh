# Env. variables to be used with Faasm and faasmctl

export PROJ_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]:-${(%):-%x}}" )" >/dev/null 2>&1 && pwd )"

export FAASM_INI_FILE=${PROJ_ROOT}/faasm.ini
export FAASM_VERSION=0.25.0
export WASM_VM=wamr
