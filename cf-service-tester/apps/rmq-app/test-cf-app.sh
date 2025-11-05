#!/bin/bash

# Script to test Cloud Foundry app with proper SSL handling
# This script provides multiple methods to handle SSL certificate issues

echo "🚀 Cloud Foundry App Testing Script"
echo "=================================="

# Check if cf CLI is available
if ! command -v cf &> /dev/null; then
    echo "❌ Cloud Foundry CLI not found. Please install it first."
    exit 1
fi

# Function to test app with different SSL approaches
test_app_endpoint() {
    local app_url=$1
    local endpoint=$2
    
    echo ""
    echo "Testing: $app_url$endpoint"
    echo "----------------------------------------"
    
    # Method 1: Try HTTPS with SSL verification
    echo "1️⃣ Testing HTTPS with SSL verification..."
    if curl -s --max-time 10 "$app_url$endpoint" > /dev/null 2>&1; then
        echo "✅ HTTPS with SSL verification: SUCCESS"
        curl -s "$app_url$endpoint" | python3 -m json.tool 2>/dev/null || curl -s "$app_url$endpoint"
        return 0
    else
        echo "❌ HTTPS with SSL verification: FAILED"
    fi
    
    # Method 2: Try HTTPS without SSL verification
    echo "2️⃣ Testing HTTPS without SSL verification..."
    if curl -k -s --max-time 10 "$app_url$endpoint" > /dev/null 2>&1; then
        echo "✅ HTTPS without SSL verification: SUCCESS"
        curl -k -s "$app_url$endpoint" | python3 -m json.tool 2>/dev/null || curl -k -s "$app_url$endpoint"
        return 0
    else
        echo "❌ HTTPS without SSL verification: FAILED"
    fi
    
    # Method 3: Try HTTP (if available)
    local http_url=${app_url/https:/http:}
    echo "3️⃣ Testing HTTP..."
    if curl -s --max-time 10 "$http_url$endpoint" > /dev/null 2>&1; then
        echo "✅ HTTP: SUCCESS"
        curl -s "$http_url$endpoint" | python3 -m json.tool 2>/dev/null || curl -s "$http_url$endpoint"
        return 0
    else
        echo "❌ HTTP: FAILED"
    fi
    
    echo "❌ All connection methods failed for $endpoint"
    return 1
}

# Get app information
echo "📋 Getting CF app information..."
if ! cf target &> /dev/null; then
    echo "❌ Not logged into Cloud Foundry. Please run 'cf login' first."
    exit 1
fi

echo "Current target:"
cf target

echo ""
echo "📱 Getting app status..."
cf apps

# Get the app URL (you may need to adjust this based on your app name)
echo ""
read -p "Enter your app URL (e.g., https://your-app.cfapps.io): " APP_URL

if [ -z "$APP_URL" ]; then
    echo "❌ No app URL provided. Exiting."
    exit 1
fi

# Test various endpoints
echo ""
echo "🧪 Testing Application Endpoints"
echo "================================="

# Test health endpoint
test_app_endpoint "$APP_URL" "/"

# Test TLS config endpoint
test_app_endpoint "$APP_URL" "/tls-config"

# Test services endpoint
test_app_endpoint "$APP_URL" "/services"

echo ""
echo "🎯 Testing Message Publishing"
echo "============================="

# Test publishing a message
echo "Testing POST /publish endpoint..."
APP_URL_CLEAN=${APP_URL%/}  # Remove trailing slash if present

# Try HTTPS with SSL skip first (most likely to work)
echo "Attempting to publish test message..."
curl -k -X POST "$APP_URL_CLEAN/publish" \
  -H "Content-Type: application/json" \
  -d '{
    "queue": "test_queue", 
    "message": {
      "text": "Test message from CF", 
      "timestamp": "'$(date -Iseconds)'",
      "source": "cf-test-script"
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n" \
  2>/dev/null | python3 -m json.tool 2>/dev/null || \
curl -k -X POST "$APP_URL_CLEAN/publish" \
  -H "Content-Type: application/json" \
  -d '{
    "queue": "test_queue", 
    "message": {
      "text": "Test message from CF", 
      "timestamp": "'$(date -Iseconds)'",
      "source": "cf-test-script"
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n"

echo ""
echo "🔍 SSL Certificate Information"
echo "=============================="
echo "To get detailed SSL certificate info:"
echo "openssl s_client -connect ${APP_URL#https://}:443 -servername ${APP_URL#https://} < /dev/null"

echo ""
echo "💡 Common Solutions for SSL Issues:"
echo "1. Use curl -k or --insecure for testing"
echo "2. Add CF platform CA certificate to your system"
echo "3. Use HTTP instead of HTTPS (if supported)"
echo "4. Contact your CF administrator about certificates"

echo ""
echo "✅ Testing complete!"
