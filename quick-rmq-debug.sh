#!/bin/bash

# Quick RMQ Debug - Focused troubleshooting

echo "🚨 Quick RMQ Connection Debug"
echo "============================="

# Get app URL
read -p "Enter your CF app URL: " APP_URL
APP_URL_CLEAN=${APP_URL%/}

echo ""
echo "📊 Current App Status:"
curl -k -s "$APP_URL_CLEAN/" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f'✅ App Status: {data[\"status\"]}')
    print(f'❌ RMQ Connected: {data[\"rmq_connected\"]}')
    print(f'🔒 SSL Enabled: {data[\"ssl_enabled\"]}')
except:
    print('❌ Could not parse health check response')
"

echo ""
echo "🔍 Checking Services Configuration:"
curl -k -s "$APP_URL_CLEAN/services" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    services = data.get('services', [])
    print(f'📋 Found {len(services)} service(s):')
    for service in services:
        print(f'  - Name: {service[\"name\"]}')
        print(f'    Label: {service[\"label\"]}')
        print(f'    Plan: {service[\"plan\"]}')
    if not services:
        print('❌ No services found! This is likely the issue.')
        print('   You need to create and bind a CUPS service.')
except Exception as e:
    print(f'❌ Error checking services: {e}')
"

echo ""
echo "🔧 Next Steps Based on Diagnosis:"
echo ""

# Check if this is a service binding issue
SERVICE_COUNT=$(curl -k -s "$APP_URL_CLEAN/services" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data.get('services', [])))
except:
    print('0')
" 2>/dev/null || echo "0")

if [ "$SERVICE_COUNT" = "0" ]; then
    echo "🎯 ISSUE IDENTIFIED: No RMQ service bound to your app"
    echo ""
    echo "SOLUTION:"
    echo "1. Create CUPS service:"
    echo "   ./setup-cups.sh"
    echo ""
    echo "2. Make sure to configure these in setup-cups.sh:"
    echo "   RMQ_HOST=\"your-rabbitmq-hostname\""
    echo "   RMQ_PORT=\"5672\"  # or 5671 for SSL"
    echo "   RMQ_USERNAME=\"your-username\""
    echo "   RMQ_PASSWORD=\"your-password\""
    echo ""
    echo "3. Restart your app:"
    echo "   cf restart your-app-name"
else
    echo "🔍 Service found, checking TLS config..."
    curl -k -s "$APP_URL_CLEAN/tls-config" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    config = data.get('tls_config', {})
    print(f'🔒 SSL Enabled: {config.get(\"ssl_enabled\", False)}')
    print(f'📍 Config Source: {config.get(\"configuration_source\", \"unknown\")}')
    print(f'🏠 CA Cert Configured: {config.get(\"ca_cert_configured\", False)}')
    print(f'👤 Client Cert Configured: {config.get(\"client_cert_configured\", False)}')
    
    if not config.get('ssl_enabled'):
        print('')
        print('💡 SSL is disabled. If you need SSL:')
        print('   1. Set RMQ_SSL_ENABLED=\"true\" in setup-cups.sh')
        print('   2. Provide certificate paths')
        print('   3. Recreate the service: ./setup-cups.sh')
except Exception as e:
    print(f'❌ Error checking TLS config: {e}')
"
fi

echo ""
echo "📝 Manual Steps to Fix:"
echo "======================"
echo ""
echo "1. Log into CF:"
echo "   cf login"
echo ""
echo "2. Check current services:"
echo "   cf services"
echo ""
echo "3. If no RMQ service exists, edit setup-cups.sh with your RMQ details:"
echo "   nano setup-cups.sh"
echo "   # Update RMQ_HOST, RMQ_USERNAME, RMQ_PASSWORD, etc."
echo ""
echo "4. Create the service:"
echo "   ./setup-cups.sh"
echo ""
echo "5. Restart your app:"
echo "   cf restart your-app-name"
echo ""
echo "6. Test again:"
echo "   curl -k $APP_URL_CLEAN/"
echo ""

echo "🆘 Still Need Help?"
echo "=================="
echo "Please provide:"
echo "1. Your RMQ instance details (host, port, credentials)"
echo "2. Output of: cf services"
echo "3. Output of: cf logs your-app-name --recent"
