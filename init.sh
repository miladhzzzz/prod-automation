#!/bin/bash


docker build -t prod-automation:latest . || {
    echo "Failed to build image..."
    exit 1
}

docker run -d --name prod-auto --privileged -v /usr/lib/systemd/system/docker.sock:/var/run/docker.sock -p 1111:1111 prod-automation:latest || {
    echo "Failed to run container..."
    exit 1
}
