#!/bin/bash

# Cloud Foundry CUPS (Cloud User-Provided Service) setup script for RabbitMQ
# This script creates a user-provided service that your CF app can bind to

# Configuration - Update these values with your actual RabbitMQ credentials
RMQ_HOST="your-rabbitmq-host.com"
RMQ_PORT="5672"  # Use 5671 for TLS/SSL
RMQ_USERNAME="your-username"
RMQ_PASSWORD="your-password"
RMQ_VHOST="/"
SERVICE_NAME="rabbitmq-service"

# TLS/SSL Configuration (optional)
# Set to "true" to enable TLS/SSL
RMQ_SSL_ENABLED="false"
# Set to "false" to disable certificate verification (not recommended for production)
RMQ_SSL_VERIFY="true"
# Paths to certificate files (optional for client certificate authentication)
RMQ_CA_CERT_PATH=""
RMQ_CLIENT_CERT_PATH=""
RMQ_CLIENT_KEY_PATH=""

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

# Build the JSON payload with TLS options
JSON_PAYLOAD='{
    "hostname": "'$RMQ_HOST'",
    "port": '$RMQ_PORT',
    "username": "'$RMQ_USERNAME'",
    "password": "'$RMQ_PASSWORD'",
    "vhost": "'$RMQ_VHOST'",
    "ssl_enabled": '$RMQ_SSL_ENABLED',
    "ssl_verify": '$RMQ_SSL_VERIFY''

# Add certificate paths if provided
if [ -n "$RMQ_CA_CERT_PATH" ]; then
    JSON_PAYLOAD=$JSON_PAYLOAD',
    "ca_cert_path": "'$RMQ_CA_CERT_PATH'"'
fi

if [ -n "$RMQ_CLIENT_CERT_PATH" ]; then
    JSON_PAYLOAD=$JSON_PAYLOAD',
    "client_cert_path": "'$RMQ_CLIENT_CERT_PATH'"'
fi

if [ -n "$RMQ_CLIENT_KEY_PATH" ]; then
    JSON_PAYLOAD=$JSON_PAYLOAD',
    "client_key_path": "'$RMQ_CLIENT_KEY_PATH'"'
fi

JSON_PAYLOAD=$JSON_PAYLOAD'}'

echo "Service configuration:"
echo "$JSON_PAYLOAD" | python3 -m json.tool 2>/dev/null || echo "$JSON_PAYLOAD"
echo ""

cf create-user-provided-service $SERVICE_NAME -p "$JSON_PAYLOAD"

if [ $? -eq 0 ]; then
    echo "✅ Successfully created user-provided service '$SERVICE_NAME'"
    echo ""
    echo "Service details:"
    cf service $SERVICE_NAME
    echo ""
    
    if [ "$RMQ_SSL_ENABLED" = "true" ]; then
        echo "🔒 TLS/SSL is ENABLED for this service"
        echo "   - Port: $RMQ_PORT (should be 5671 for TLS)"
        echo "   - Certificate verification: $RMQ_SSL_VERIFY"
        if [ -n "$RMQ_CA_CERT_PATH" ]; then
            echo "   - CA Certificate: $RMQ_CA_CERT_PATH"
        fi
        if [ -n "$RMQ_CLIENT_CERT_PATH" ]; then
            echo "   - Client Certificate: $RMQ_CLIENT_CERT_PATH"
        fi
    else
        echo "🔓 TLS/SSL is DISABLED for this service"
        echo "   - Port: $RMQ_PORT (standard non-SSL port is 5672)"
    fi
    
    echo ""
    echo "You can now deploy your app with:"
    echo "  cf push"
    echo ""
    echo "The app will automatically bind to the '$SERVICE_NAME' service as specified in manifest.yml"
    echo ""
    echo "To test TLS configuration locally, set these environment variables:"
    echo "  export RMQ_SSL_ENABLED=$RMQ_SSL_ENABLED"
    echo "  export RMQ_SSL_VERIFY=$RMQ_SSL_VERIFY"
    if [ -n "$RMQ_CA_CERT_PATH" ]; then
        echo "  export RMQ_CA_CERT_PATH=$RMQ_CA_CERT_PATH"
    fi
    if [ -n "$RMQ_CLIENT_CERT_PATH" ]; then
        echo "  export RMQ_CLIENT_CERT_PATH=$RMQ_CLIENT_CERT_PATH"
    fi
    if [ -n "$RMQ_CLIENT_KEY_PATH" ]; then
        echo "  export RMQ_CLIENT_KEY_PATH=$RMQ_CLIENT_KEY_PATH"
    fi
else
    echo "❌ Failed to create user-provided service"
    exit 1
fi
