#!/bin/bash

set -e

# Run hoststats in the background
nohup hoststats start > /var/log/hoststats.log 2>&1 &

# Run sshd in the background. Running in the foreground makes container
# impossible to kill nicely
echo "Running sshd in background"
/sshd_wrapper.sh 2>&1 > /var/log/sshd &

# Wait for sshd to be up
sleep 5
echo "Wrapper script started"

# Foreground sleep which can be killed nicely
sleep infinity

echo "Wrapper script finished"
