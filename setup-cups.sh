#!/bin/bash

# Cloud Foundry CUPS (Cloud User-Provided Service) setup script for RabbitMQ
# This script creates a user-provided service that your CF app can bind to

# Configuration - Update these values with your actual RabbitMQ credentials
RMQ_HOST="your-rabbitmq-host.com"
RMQ_PORT="5672"
RMQ_USERNAME="your-username"
RMQ_PASSWORD="your-password"
RMQ_VHOST="/"
SERVICE_NAME="rabbitmq-service"

echo "Setting up Cloud User-Provided Service (CUPS) for RabbitMQ..."

# Check if cf CLI is installed
if ! command -v cf &> /dev/null; then
    echo "Error: Cloud Foundry CLI (cf) is not installed or not in PATH"
    echo "Please install it from: https://docs.cloudfoundry.org/cf-cli/install-go-cli.html"
    exit 1
fi

# Check if user is logged in
if ! cf target &> /dev/null; then
    echo "Error: You are not logged into Cloud Foundry"
    echo "Please run 'cf login' first"
    exit 1
fi

echo "Current CF target:"
cf target

# Create the CUPS service with RabbitMQ credentials
echo "Creating user-provided service '$SERVICE_NAME'..."

cf create-user-provided-service $SERVICE_NAME -p '{
    "hostname": "'$RMQ_HOST'",
    "port": '$RMQ_PORT',
    "username": "'$RMQ_USERNAME'",
    "password": "'$RMQ_PASSWORD'",
    "vhost": "'$RMQ_VHOST'"
}'

if [ $? -eq 0 ]; then
    echo "✅ Successfully created user-provided service '$SERVICE_NAME'"
    echo ""
    echo "Service details:"
    cf service $SERVICE_NAME
    echo ""
    echo "You can now deploy your app with:"
    echo "  cf push"
    echo ""
    echo "The app will automatically bind to the '$SERVICE_NAME' service as specified in manifest.yml"
else
    echo "❌ Failed to create user-provided service"
    exit 1
fi
