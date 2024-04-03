#!/bin/bash

# Set default values
context="default"
api_server_url=""

# Parse command-line options
while getopts ":c:a:k:" opt; do
  case $opt in
    c)
      context="$OPTARG"
      ;;
    a)
      api_server_url="$OPTARG"
      ;;
    k)
      kubeconfig_file="$OPTARG"
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
  esac
done

kubeconfig_file="${context}-kubeconfig.yaml"

# Check if API server URL is provided
if [ -z "$api_server_url" ]; then
  echo "API server URL is required."
  exit 1
fi

# Get kubeconfig from context
kubectl config use-context $context
kubectl config view --minify --flatten --context=$context > $kubeconfig_file

# Upload kubeconfig to API server
curl -X POST -H "Content-Type: multipart/form-data" -F "file=@$kubeconfig_file" $api_server_url/upload

rm $kubeconfig_file

echo "Kubeconfig uploaded successfully!"