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

# Set execute permissions for scripts
chmod +x ./scripts/setup-host.sh
chmod +x ./scripts/env_set.sh
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

# Step 5: Deploy project components
if ! make up; then
    handle_error "Failed to deploy project components"
fi

# Step 6: Execute env_set.sh with GitHub webhook secret
if ! ./scripts/env_set.sh "GITHUB_WEBHOOK_SECRET" "$1"; then
    handle_error "Failed to execute env_set.sh"
fi

# Step 7: Execute hosts-registry.sh with arguments insecure_registry and update_hosts
if ! ./scripts/hosts-registry.sh insecure_registry; then
    handle_error "Failed to execute hosts-registry.sh with insecure_registry"
fi

if ! ./scripts/hosts-registry.sh update_hosts; then
    handle_error "Failed to execute hosts-registry.sh with update_hosts"
fi

# Step 8: Setup cronjob for Docker image prune
(crontab -l ; echo "0 0 * * * docker image prune -a -f") | crontab -
