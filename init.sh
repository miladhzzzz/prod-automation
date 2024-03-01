#!/bin/bash

# Check if Docker, Docker Compose, and Git are installed
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null || ! command -v git &> /dev/null; then
    echo "Required dependencies are not installed. Running setup-host.sh..."
    # Execute the setup-host.sh script
    bash ./scripts/setup-host.sh
else
    echo "Required dependencies are already installed."
fi

# Ensure latest upstream version
git pull || {
    echo "Failed running git pull."
}

# Check if a container with the same name exists and stop and remove it
if docker ps -a --format '{{.Names}}' | grep -q "^prod-auto"; then
    echo "Found the old Container...Removing!"
    docker stop prod-auto
    docker rm prod-auto
fi

# Build docker container
docker build -t prod-automation:latest . || {
    echo "Failed to build image..."
    exit 1
}

# Run docker container PRIVILEGED MODE !!! we are mounting host os Docker Server to the automation container
docker run -d --name prod-auto --privileged -v /var/run/docker.sock:/var/run/docker.sock -p 1111:1111 prod-automation:latest || {
    echo "Failed to run container..."
    exit 1
}
