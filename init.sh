#!/bin/bash

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to handle errors
handle_error() {
    echo "Error: $1"
    exit 1
}

# Check if project containers are running and issue make down command
if docker ps | grep -q "prod-automation_prod-auto_1"; then
    make down
fi

# Set execute permissions for scripts
chmod +x ./scripts/setup-host.sh
chmod +x ./scripts/env-set.sh
chmod +x ./scripts/hosts-registry.sh

# Check if Docker, Docker Compose, and Git are installed
if ! command_exists docker || ! command_exists docker-compose || ! command_exists git; then
    echo "Docker, Docker Compose, or Git is not installed. Running setup script..."
    if ! ./scripts/setup-host.sh; then
        handle_error "Failed to setup host environment"
    fi
fi

# Step 1: Get GitHub webhook secret from user
if [ -z "$1" ]; then
    handle_error "Please provide the GitHub webhook secret as an argument"
fi

# Step 2: Sync to upstream
if ! git pull; then
    handle_error "Failed to sync with upstream repository"
fi

# Step 3: Build project image
if ! make build; then
    handle_error "Failed to build the project image"
fi

# Step 4: Build secret key
if ! make keygen; then
    handle_error "Failed to build the secret key"
fi

# Step 5: Execute hosts-registry.sh
if ! ./scripts/hosts-registry.sh insecure_registry; then
    handle_error "Failed to execute hosts-registry.sh with insecure_registry"
fi

# Step 6: Deploy project components
if ! make up; then
    handle_error "Failed to deploy project components"
fi

# Step 7: Execute env-set.sh with GitHub webhook secret
if ! ./scripts/env-set.sh GITHUB_WEBHOOK_SECRET "$1"; then
    handle_error "Failed to execute env-set.sh"
fi

# step 8: Update host /etc/hosts file with new container ip
if ! ./scripts/hosts-registry.sh update_hosts; then
    handle_error "Failed to execute hosts-registry.sh with update_hosts"
fi

# Check if cronjob exists
if ! crontab -l | grep -q "docker image prune"; then
    # Setup cronjob for Docker image prune
    (crontab -l ; echo "0 0 * * * docker image prune -a -f") | crontab -
fi