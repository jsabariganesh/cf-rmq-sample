#!/bin/bash

# Script to test certificate content handling
# This script demonstrates how certificates are embedded in CUPS service

echo "🧪 Testing Certificate Content Handling"
echo "======================================"

# Check if certificates exist
CERT_DIR="./certs"
if [ ! -d "$CERT_DIR" ]; then
    echo "❌ Certificate directory not found. Run ./generate-test-certs.sh first"
    exit 1
fi

CA_CERT="$CERT_DIR/ca-cert.pem"
CLIENT_CERT="$CERT_DIR/client-cert.pem"
CLIENT_KEY="$CERT_DIR/client-key.pem"

if [ ! -f "$CA_CERT" ] || [ ! -f "$CLIENT_CERT" ] || [ ! -f "$CLIENT_KEY" ]; then
    echo "❌ Certificate files not found. Run ./generate-test-certs.sh first"
    exit 1
fi

echo "📋 Certificate files found:"
echo "   - CA Certificate: $CA_CERT"
echo "   - Client Certificate: $CLIENT_CERT"
echo "   - Client Key: $CLIENT_KEY"
echo ""

# Function to read and encode certificate content (same as in setup-cups.sh)
read_cert_content() {
    local cert_path=$1
    if [ -n "$cert_path" ] && [ -f "$cert_path" ]; then
        # Read certificate content and escape newlines and quotes for JSON
        cat "$cert_path" | sed 's/$/\\n/' | tr -d '\n' | sed 's/\\n$//' | sed 's/"/\\"/g'
    else
        echo ""
    fi
}

echo "🔍 Testing certificate content reading:"
echo ""

# Test CA certificate
echo "1. CA Certificate content (first 100 characters):"
CA_CONTENT=$(read_cert_content "$CA_CERT")
echo "${CA_CONTENT:0:100}..."
echo "   Length: ${#CA_CONTENT} characters"
echo ""

# Test Client certificate
echo "2. Client Certificate content (first 100 characters):"
CLIENT_CERT_CONTENT=$(read_cert_content "$CLIENT_CERT")
echo "${CLIENT_CERT_CONTENT:0:100}..."
echo "   Length: ${#CLIENT_CERT_CONTENT} characters"
echo ""

# Test Client key
echo "3. Client Key content (first 100 characters):"
CLIENT_KEY_CONTENT=$(read_cert_content "$CLIENT_KEY")
echo "${CLIENT_KEY_CONTENT:0:100}..."
echo "   Length: ${#CLIENT_KEY_CONTENT} characters"
echo ""

# Create a test JSON payload (similar to CUPS)
echo "📝 Creating test JSON payload:"
TEST_JSON='{
    "hostname": "test-host",
    "port": 5671,
    "ssl_enabled": true,
    "ca_cert_content": "'$CA_CONTENT'",
    "client_cert_content": "'$CLIENT_CERT_CONTENT'",
    "client_key_content": "'$CLIENT_KEY_CONTENT'"
}'

echo "JSON payload size: $(echo "$TEST_JSON" | wc -c) bytes"
echo ""

# Test environment variable approach
echo "🌍 Testing environment variable approach:"
echo "export RMQ_SSL_ENABLED=true"
echo "export RMQ_CA_CERT_CONTENT='$CA_CONTENT'"
echo "export RMQ_CLIENT_CERT_CONTENT='$CLIENT_CERT_CONTENT'"
echo "export RMQ_CLIENT_KEY_CONTENT='$CLIENT_KEY_CONTENT'"
echo ""

# Test the conversion back to files
echo "🔄 Testing content to file conversion:"
TEMP_DIR=$(mktemp -d)
echo "Using temp directory: $TEMP_DIR"

# Convert content back to files
echo "$CA_CONTENT" | sed 's/\\n/\n/g' > "$TEMP_DIR/ca-cert.pem"
echo "$CLIENT_CERT_CONTENT" | sed 's/\\n/\n/g' > "$TEMP_DIR/client-cert.pem"
echo "$CLIENT_KEY_CONTENT" | sed 's/\\n/\n/g' > "$TEMP_DIR/client-key.pem"

# Verify the converted files
echo "Verifying converted certificates:"
if openssl x509 -in "$TEMP_DIR/ca-cert.pem" -noout -subject 2>/dev/null; then
    echo "✅ CA certificate conversion successful"
    openssl x509 -in "$TEMP_DIR/ca-cert.pem" -noout -subject
else
    echo "❌ CA certificate conversion failed"
fi

if openssl x509 -in "$TEMP_DIR/client-cert.pem" -noout -subject 2>/dev/null; then
    echo "✅ Client certificate conversion successful"
    openssl x509 -in "$TEMP_DIR/client-cert.pem" -noout -subject
else
    echo "❌ Client certificate conversion failed"
fi

if openssl rsa -in "$TEMP_DIR/client-key.pem" -noout -check 2>/dev/null; then
    echo "✅ Client key conversion successful"
else
    echo "❌ Client key conversion failed"
fi

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "✅ Certificate content handling test completed!"
echo ""
echo "💡 Key points:"
echo "   - Certificates are embedded as escaped strings in CUPS service"
echo "   - App creates temporary files from certificate content"
echo "   - Temporary files are cleaned up after use"
echo "   - This approach works in CF containers without file system access"
