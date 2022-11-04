#!/bin/bash

set -e

echo "Setting up venv at $(pwd)/venv"
python3.8 -m venv venv
source venv/bin/activate
pip3 install -U pip
pip3 install -r requirements.txt
