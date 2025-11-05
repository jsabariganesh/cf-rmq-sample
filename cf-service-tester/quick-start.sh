#!/bin/bash

# Cloud Foundry Service Tester - Quick Start Script
# This script helps you get started with the CF Service Tester framework

set -e

echo "🚀 Cloud Foundry Service Tester - Quick Start"
echo "=============================================="

# Check if CF CLI is installed
if ! command -v cf &> /dev/null; then
    echo "❌ Cloud Foundry CLI not found. Please install it first:"
    echo "   https://docs.cloudfoundry.org/cf-cli/install-go-cli.html"
    exit 1
fi

# Check if logged into CF
if ! cf target &> /dev/null; then
    echo "❌ Not logged into Cloud Foundry. Please run 'cf login' first."
    exit 1
fi

echo "✅ CF CLI found and logged in"
echo "Current target:"
cf target

echo ""
echo "📋 Available Configuration Templates:"
echo "1. Minimal (In-memory database only) - Fastest deployment"
echo "2. PostgreSQL Marketplace - Test marketplace database service"
echo "3. Full Stack - All services (PostgreSQL + RabbitMQ + Redis)"
echo "4. Custom - Use existing config/app_config.yaml"

read -p "Choose configuration (1-4): " choice

case $choice in
    1)
        echo "📝 Using minimal configuration..."
        cp config/examples/minimal.yaml config/app_config.yaml
        APP_NAME="cf-test-minimal"
        ;;
    2)
        echo "📝 Using PostgreSQL marketplace configuration..."
        cp config/examples/postgres-marketplace.yaml config/app_config.yaml
        APP_NAME="cf-test-postgres"
        
        echo ""
        echo "⚠️  Please verify the PostgreSQL service name and plan in your CF marketplace:"
        echo "   cf marketplace"
        echo ""
        read -p "Press Enter to continue or Ctrl+C to edit config/app_config.yaml first..."
        ;;
    3)
        echo "📝 Using full stack configuration..."
        cp config/examples/full-stack.yaml config/app_config.yaml
        APP_NAME="cf-test-fullstack"
        
        echo ""
        echo "⚠️  Full stack requires:"
        echo "   - PostgreSQL marketplace service"
        echo "   - Redis marketplace service"
        echo "   - RabbitMQ certificates in apps/rmq-app/certs/"
        echo ""
        echo "To generate test certificates for RabbitMQ:"
        echo "   cd apps/rmq-app && ./generate-test-certs.sh"
        echo ""
        read -p "Press Enter to continue or Ctrl+C to prepare certificates first..."
        ;;
    4)
        echo "📝 Using existing config/app_config.yaml..."
        if [ ! -f "config/app_config.yaml" ]; then
            echo "❌ config/app_config.yaml not found. Please create it first."
            exit 1
        fi
        
        # Extract app name from config
        APP_NAME=$(python3 -c "
import yaml
with open('config/app_config.yaml', 'r') as f:
    config = yaml.safe_load(f)
print(config['app']['name'])
" 2>/dev/null || echo "cf-service-tester")
        ;;
    *)
        echo "❌ Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "🔍 Configuration Summary:"
echo "========================"
python3 -c "
import yaml
with open('config/app_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

print(f\"App Name: {config['app']['name']}\")
print(f\"Description: {config['app']['description']}\")
print(f\"Database: {config['database']['type']} ({config['database']['connection_type']})\")
print(f\"Message Queue: {'Enabled' if config.get('message_queue', {}).get('enabled', False) else 'Disabled'}\")
print(f\"Cache: {'Enabled' if config.get('cache', {}).get('enabled', False) else 'Disabled'}\")
"

echo ""
read -p "Proceed with deployment? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "❌ Deployment cancelled."
    echo ""
    echo "💡 To customize configuration:"
    echo "   vim config/app_config.yaml"
    echo ""
    echo "💡 To deploy manually:"
    echo "   python deploy.py"
    exit 0
fi

echo ""
echo "🚀 Starting deployment..."
echo "========================"

# Run deployment
if python deploy.py; then
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "🌐 Access your application:"
    echo "   Web UI: https://${APP_NAME}.cfapps.io/ui"
    echo "   Health: https://${APP_NAME}.cfapps.io/health"
    echo "   API:    https://${APP_NAME}.cfapps.io/api/reservations"
    echo ""
    echo "📊 Quick Tests:"
    echo "   curl -k https://${APP_NAME}.cfapps.io/health"
    echo "   curl -k https://${APP_NAME}.cfapps.io/services"
    echo ""
    echo "🔧 CF Management:"
    echo "   cf app ${APP_NAME}"
    echo "   cf logs ${APP_NAME} --recent"
    echo "   cf env ${APP_NAME}"
    
    # Try to open the web UI
    if command -v open &> /dev/null; then
        read -p "Open web UI in browser? (y/N): " open_ui
        if [[ $open_ui == [yY] || $open_ui == [yY][eE][sS] ]]; then
            open "https://${APP_NAME}.cfapps.io/ui"
        fi
    fi
    
else
    echo ""
    echo "❌ Deployment failed!"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "   1. Check CF login: cf target"
    echo "   2. Check marketplace: cf marketplace"
    echo "   3. Check logs: cf logs ${APP_NAME} --recent"
    echo "   4. Verify config: cat config/app_config.yaml"
    echo ""
    echo "💡 For help, see README.md or run:"
    echo "   python deploy.py --dry-run"
    exit 1
fi
