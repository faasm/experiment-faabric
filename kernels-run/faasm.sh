#!/bin/bash
# Note: you may need to re-build the container if the k8s cluster has been
# reset by running `./bin/build_faasm.sh`.

set -e

THIS_DIR=$(dirname $(readlink -f $0))
PROJ_ROOT=${THIS_DIR}/..

pushd ${PROJ_ROOT} >> /dev/null

# Run benchmark
python3 run/all_faasm.py | tee logs/http_reqs.log
elapsed_mins=$(tail -1 logs/http_reqs.log)
echo "Elapsed mins: ${elapsed_mins}"

# Parse the output for results
kubectl logs -n faasm \
    --since="${elapsed_mins}m" \
    --tail=-1 \
    -l serving.knative.dev/service=faasm-worker \
    -c user-container | tee logs/k8s_out.log | python3 run/util/parse_output.py

popd >> /dev/null

