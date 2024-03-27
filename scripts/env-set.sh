#!/bin/bash

# Check if the argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <ENV_VARIABLE_NAME>"
    exit 1
fi

# Set the environment variable inside the Docker container
docker exec prod-automation_prod-auto_1 sh -c "export $1=$2"

echo "Environment variable $1 set to $2 inside the container."
