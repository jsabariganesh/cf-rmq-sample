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

# Function to read and encode certificate content
read_cert_content() {
    local cert_path=$1
    if [ -n "$cert_path" ] && [ -f "$cert_path" ]; then
        # Read certificate content and escape newlines and quotes for JSON
        cat "$cert_path" | sed 's/$/\\n/' | tr -d '\n' | sed 's/\\n$//' | sed 's/"/\\"/g'
    else
        echo ""
    fi
}

# Build the JSON payload with TLS options
JSON_PAYLOAD='{
    "hostname": "'$RMQ_HOST'",
    "port": '$RMQ_PORT',
    "username": "'$RMQ_USERNAME'",
    "password": "'$RMQ_PASSWORD'",
    "vhost": "'$RMQ_VHOST'",
    "ssl_enabled": '$RMQ_SSL_ENABLED',
    "ssl_verify": '$RMQ_SSL_VERIFY''

# Add certificate contents if files are provided
if [ -n "$RMQ_CA_CERT_PATH" ] && [ -f "$RMQ_CA_CERT_PATH" ]; then
    echo "Reading CA certificate from: $RMQ_CA_CERT_PATH"
    CA_CERT_CONTENT=$(read_cert_content "$RMQ_CA_CERT_PATH")
    if [ -n "$CA_CERT_CONTENT" ]; then
        JSON_PAYLOAD=$JSON_PAYLOAD',
    "ca_cert_content": "'$CA_CERT_CONTENT'"'
    else
        echo "Warning: Could not read CA certificate file"
    fi
fi

if [ -n "$RMQ_CLIENT_CERT_PATH" ] && [ -f "$RMQ_CLIENT_CERT_PATH" ]; then
    echo "Reading client certificate from: $RMQ_CLIENT_CERT_PATH"
    CLIENT_CERT_CONTENT=$(read_cert_content "$RMQ_CLIENT_CERT_PATH")
    if [ -n "$CLIENT_CERT_CONTENT" ]; then
        JSON_PAYLOAD=$JSON_PAYLOAD',
    "client_cert_content": "'$CLIENT_CERT_CONTENT'"'
    else
        echo "Warning: Could not read client certificate file"
    fi
fi

if [ -n "$RMQ_CLIENT_KEY_PATH" ] && [ -f "$RMQ_CLIENT_KEY_PATH" ]; then
    echo "Reading client private key from: $RMQ_CLIENT_KEY_PATH"
    CLIENT_KEY_CONTENT=$(read_cert_content "$RMQ_CLIENT_KEY_PATH")
    if [ -n "$CLIENT_KEY_CONTENT" ]; then
        JSON_PAYLOAD=$JSON_PAYLOAD',
    "client_key_content": "'$CLIENT_KEY_CONTENT'"'
    else
        echo "Warning: Could not read client private key file"
    fi
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
        if [ -n "$RMQ_CA_CERT_PATH" ] && [ -f "$RMQ_CA_CERT_PATH" ]; then
            echo "   - CA Certificate: Embedded from $RMQ_CA_CERT_PATH"
        fi
        if [ -n "$RMQ_CLIENT_CERT_PATH" ] && [ -f "$RMQ_CLIENT_CERT_PATH" ]; then
            echo "   - Client Certificate: Embedded from $RMQ_CLIENT_CERT_PATH"
        fi
        if [ -n "$RMQ_CLIENT_KEY_PATH" ] && [ -f "$RMQ_CLIENT_KEY_PATH" ]; then
            echo "   - Client Key: Embedded from $RMQ_CLIENT_KEY_PATH"
        fi
        echo "   - Certificate contents are embedded in service credentials"
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
