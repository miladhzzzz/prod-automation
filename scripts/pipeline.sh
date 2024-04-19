#!/usr/bin/env bash

set -euo pipefail

# Webhook secret
WEBHOOK_SECRET=$1

# Define the port to listen on
PORT=8888

# Log successful listening
echo "Webhook handler is now listening on port $PORT..."

# Start listening for incoming webhook payloads
while true; do
    # Use netcat to listen for incoming HTTP POST requests
    request=$(echo -ne "HTTP/1.1 200 OK\r\n\r\n" | nc -l -p $PORT)

    # Extract headers and request body
    headers=$(echo "$request" | awk 'BEGIN {RS="\r\n\r\n"} {print; exit}')
    body=$(echo "$request" | awk 'BEGIN {RS="\r\n\r\n"} {getline; print}')

    # Extract X-GitHub-Event from headers
    github_event=$(echo "$headers" | grep -i '^X-GitHub-Event:' | awk '{print $2}' | tr -d '[:space:]')

    # Log received headers, body, and GitHub event
    echo "Received headers: $headers"
    echo "Received body: $body"
    echo "GitHub Event: $github_event"

    # Example: Extract repository name from the body
    repo_name=$(echo "$body" | jq -r '.repository.name')

    # Example: Extract commit hash from the body
    commit_hash=$(echo "$body" | jq -r '.after')

    # Log trigger details
    echo "Trigger: Webhook"
    echo "Repository: $repo_name"
    echo "Commit Hash: $commit_hash"

    # Example: Trigger appropriate CI/CD scripts based on event type
    case "$github_event" in  
        "push")
            echo "Event Type: Push"
            ../init.sh "$WEBHOOK_SECRET"
            ;;
        "pull_request")
            echo "Event Type: Pull Request"
            ./build.sh
            ./test.sh
            ;;
        # Add more cases for other event types as needed
        *)
            echo "Unsupported event type: $github_event"
            ;;
    esac
done
