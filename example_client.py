#!/usr/bin/env python3
"""
Example client script to interact with the CF Python RMQ App
This script demonstrates how to use the API endpoints.
"""

import requests
import json
import time
from datetime import datetime

# Configuration - Update with your app URL
APP_URL = "http://localhost:5000"  # Change to your CF app URL when deployed
# APP_URL = "https://your-app.cfapps.io"

def health_check():
    """Check application health"""
    print("🏥 Checking application health...")
    try:
        response = requests.get(f"{APP_URL}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def publish_message(queue_name, message):
    """Publish a message to RabbitMQ"""
    print(f"📤 Publishing message to queue '{queue_name}'...")
    try:
        payload = {
            "queue": queue_name,
            "message": message
        }
        response = requests.post(f"{APP_URL}/publish", json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed to publish message: {e}")
        return False

def get_queue_info(queue_name):
    """Get queue information"""
    print(f"📊 Getting info for queue '{queue_name}'...")
    try:
        response = requests.get(f"{APP_URL}/queue/{queue_name}/info")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed to get queue info: {e}")
        return False

def list_services():
    """List bound services"""
    print("🔗 Listing bound services...")
    try:
        response = requests.get(f"{APP_URL}/services")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed to list services: {e}")
        return False

def check_tls_config():
    """Check TLS configuration"""
    print("🔒 Checking TLS configuration...")
    try:
        response = requests.get(f"{APP_URL}/tls-config")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed to check TLS config: {e}")
        return False

def main():
    """Main demonstration function"""
    print("🚀 CF Python RMQ App Client Demo")
    print("=" * 40)
    
    # Health check
    if not health_check():
        print("❌ Application is not healthy. Exiting.")
        return
    
    print("\n" + "=" * 40)
    
    # List services
    list_services()
    
    print("\n" + "=" * 40)
    
    # Check TLS configuration
    check_tls_config()
    
    print("\n" + "=" * 40)
    
    # Publish some test messages
    test_queue = "demo_queue"
    
    messages = [
        {
            "id": 1,
            "text": "Hello from the client demo!",
            "timestamp": datetime.now().isoformat(),
            "type": "greeting"
        },
        {
            "id": 2,
            "text": "This is a test message",
            "timestamp": datetime.now().isoformat(),
            "type": "test",
            "data": {"key": "value", "number": 42}
        },
        {
            "id": 3,
            "text": "Final demo message",
            "timestamp": datetime.now().isoformat(),
            "type": "farewell",
            "priority": "high"
        }
    ]
    
    for i, message in enumerate(messages, 1):
        print(f"\n📤 Publishing message {i}/3:")
        publish_message(test_queue, message)
        time.sleep(1)  # Small delay between messages
    
    print("\n" + "=" * 40)
    
    # Check queue info
    get_queue_info(test_queue)
    
    print("\n🎉 Demo completed!")

if __name__ == "__main__":
    main()
