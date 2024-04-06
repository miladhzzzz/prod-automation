#!/bin/bash

# Function to configure insecure registry
configure_insecure_registry() {
    if [ -f /etc/docker/daemon.json ]; then
        echo "daemon.json already exists. Skipping insecure registry configuration."
    else
        echo '{
          "insecure-registries": ["registry:5000"]
        }' > /etc/docker/daemon.json || {
            echo "Failed to setup insecure registry"
            exit 1
        }
        restart_docker_service
        echo "Added Insecure registry to docker..."
    fi
}

# Function to restart Docker service
restart_docker_service() {
    systemctl restart docker || {
        echo "Failed to restart Docker service"
        exit 1
    }
}

# Function to get container IP address
get_container_ip() {
    container_ip=$(docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' prod-automation_registry_1) || {
        echo "Failed to get container IP address"
        exit 1
    }
    echo "Container IP address: $container_ip"
}

# Function to update /etc/hosts with container IP address
update_hosts_file() {
    if grep -q "registry" /etc/hosts; then
        sed -i "/registry/s/.*/$container_ip registry/" /etc/hosts || {
            echo "Failed to update /etc/hosts"
            exit 1
        }
        echo "Container IP address updated in /etc/hosts: $container_ip registry"
    else
        echo "$container_ip registry" >> /etc/hosts || {
            echo "Failed to update /etc/hosts"
            exit 1
        }
        echo "Container IP address added to /etc/hosts: $container_ip registry"
    fi
}

# Main script
if [ "$1" == "insecure_registry" ]; then
    configure_insecure_registry
elif [ "$1" == "update_hosts" ]; then
    get_container_ip
    update_hosts_file
else
    echo "Usage: $0 [insecure_registry|update_hosts]"
    exit 1
fi
