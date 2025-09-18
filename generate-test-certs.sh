#!/bin/bash

# Generate self-signed certificates for RabbitMQ TLS testing
# WARNING: These are for DEVELOPMENT/TESTING only - DO NOT use in production!

CERT_DIR="./certs"
DAYS=365

echo "🔐 Generating test certificates for RabbitMQ TLS..."
echo "WARNING: These are self-signed certificates for TESTING only!"
echo ""

# Create certs directory if it doesn't exist
mkdir -p $CERT_DIR

# Generate CA private key
echo "1. Generating CA private key..."
openssl genrsa -out $CERT_DIR/ca-key.pem 4096

# Generate CA certificate
echo "2. Generating CA certificate..."
openssl req -new -x509 -days $DAYS -key $CERT_DIR/ca-key.pem -sha256 -out $CERT_DIR/ca-cert.pem -subj "/C=US/ST=Test/L=Test/O=Test CA/CN=Test CA"

# Generate server private key
echo "3. Generating server private key..."
openssl genrsa -out $CERT_DIR/server-key.pem 4096

# Generate server certificate signing request
echo "4. Generating server certificate signing request..."
openssl req -subj "/C=US/ST=Test/L=Test/O=Test/CN=localhost" -new -key $CERT_DIR/server-key.pem -out $CERT_DIR/server.csr

# Generate server certificate signed by CA
echo "5. Generating server certificate..."
openssl x509 -req -days $DAYS -in $CERT_DIR/server.csr -CA $CERT_DIR/ca-cert.pem -CAkey $CERT_DIR/ca-key.pem -out $CERT_DIR/server-cert.pem -extensions v3_req -extfile <(
cat <<EOF
[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF
)

# Generate client private key
echo "6. Generating client private key..."
openssl genrsa -out $CERT_DIR/client-key.pem 4096

# Generate client certificate signing request
echo "7. Generating client certificate signing request..."
openssl req -subj "/C=US/ST=Test/L=Test/O=Test Client/CN=client" -new -key $CERT_DIR/client-key.pem -out $CERT_DIR/client.csr

# Generate client certificate signed by CA
echo "8. Generating client certificate..."
openssl x509 -req -days $DAYS -in $CERT_DIR/client.csr -CA $CERT_DIR/ca-cert.pem -CAkey $CERT_DIR/ca-key.pem -out $CERT_DIR/client-cert.pem

# Clean up CSR files
rm $CERT_DIR/server.csr $CERT_DIR/client.csr

# Set appropriate permissions
chmod 600 $CERT_DIR/*-key.pem
chmod 644 $CERT_DIR/*-cert.pem

echo ""
echo "✅ Certificate generation complete!"
echo ""
echo "Generated files in $CERT_DIR/:"
echo "  📄 ca-cert.pem      - CA certificate (for verification)"
echo "  🔑 ca-key.pem       - CA private key"
echo "  📄 server-cert.pem  - Server certificate"
echo "  🔑 server-key.pem   - Server private key"
echo "  📄 client-cert.pem  - Client certificate"
echo "  🔑 client-key.pem   - Client private key"
echo ""
echo "To use these certificates with your RabbitMQ app:"
echo "  export RMQ_SSL_ENABLED=true"
echo "  export RMQ_CA_CERT_PATH=$PWD/$CERT_DIR/ca-cert.pem"
echo "  export RMQ_CLIENT_CERT_PATH=$PWD/$CERT_DIR/client-cert.pem"
echo "  export RMQ_CLIENT_KEY_PATH=$PWD/$CERT_DIR/client-key.pem"
echo "  export RMQ_SSL_VERIFY=false  # For self-signed certs"
echo ""
echo "For RabbitMQ server configuration, use:"
echo "  - CA certificate: $PWD/$CERT_DIR/ca-cert.pem"
echo "  - Server certificate: $PWD/$CERT_DIR/server-cert.pem"
echo "  - Server key: $PWD/$CERT_DIR/server-key.pem"
echo ""
echo "⚠️  REMEMBER: These are self-signed certificates for TESTING only!"
echo "   For production, use certificates from a trusted CA."
