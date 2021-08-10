#!/bin/bash

set -e

echo "Starting sshd..."
/usr/sbin/sshd -eD

echo "sshd shut down"
