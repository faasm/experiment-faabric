#!/bin/bash

set -e

# Check all files
FILES_TO_CHECK=$(git ls-files -- "*.py")

# Run black
python3 -m black  ${FILES_TO_CHECK}
