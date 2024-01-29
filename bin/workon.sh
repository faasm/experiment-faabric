#!/bin/bash

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]:-${(%):-%x}}" )" >/dev/null 2>&1 && pwd )"
PROJ_ROOT="${THIS_DIR}/.."

pushd ${PROJ_ROOT} >> /dev/null

export VIRTUAL_ENV_DISABLE_PROMPT=1

if [ ! -d "venv" ]; then
    ./bin/create_venv.sh
fi

source venv/bin/activate
source ./env.sh

# Invoke tab-completion
_complete_invoke() {
    local candidates
    candidates=`invoke --complete -- ${COMP_WORDS[*]}`
    COMPREPLY=( $(compgen -W "${candidates}" -- $2) )
}

# If running from zsh, run autoload for tab completion
if [ "$(ps -o comm= -p $$)" = "zsh" ]; then
    autoload bashcompinit
    bashcompinit
fi
complete -F _complete_invoke -o default invoke inv

# Pick up project-specific binaries
export PATH=${PROJ_ROOT}/bin:${PATH}
export PS1="(faasm-exp-faabric) $PS1"

# Experiment-specific variables
export FAASM_INI_FILE=${PROJ_ROOT}/faasm.ini
export FAASM_WASM_VM=wamr
export FAASM_VERSION=0.20.1

popd >> /dev/null

