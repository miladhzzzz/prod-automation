#!/bin/bash

git pull


# Check if a container with the same name exists and stop and remove it
if docker ps -a --format '{{.Names}}' | grep -q "^prod-auto"; then
   echo "Found the old Container...Removing!"
   docker stop prod-auto
   docker rm prot-auto
fi

# build docker container
docker build -t prod-automation:latest . || {
    echo "Failed to build image..."
    exit 1
}

# run docker container
docker run -d --name prod-auto --privileged -v /usr/lib/systemd/system/docker.sock:/var/run/docker.sock -p 1111:1111 prod-automation:latest || {
    echo "Failed to run container..."
    exit 1
}
