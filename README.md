# Cloud Foundry Python RabbitMQ Application

A Python Flask application designed to run on Cloud Foundry with RabbitMQ connectivity via Cloud User-Provided Services (CUPS).

## Features

- **Flask Web Application**: RESTful API endpoints for RabbitMQ operations
- **RabbitMQ Integration**: Connect to RabbitMQ using pika library
- **CUPS Support**: Automatic service discovery from Cloud Foundry bound services
- **Health Checks**: Built-in health check endpoint
- **Message Publishing**: Publish messages to RabbitMQ queues
- **Queue Management**: Get queue information and statistics
- **Environment Flexibility**: Works both on Cloud Foundry and locally

## Project Structure

```
cf-python-rmq-app/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── manifest.yml        # Cloud Foundry deployment configuration
├── setup-cups.sh       # Script to create CUPS service
└── README.md          # This file
```

## Prerequisites

- Python 3.8+
- Cloud Foundry CLI
- Access to a Cloud Foundry environment
- RabbitMQ instance (can be external)

## Local Development Setup

1. **Clone and navigate to the project:**
   ```bash
   cd cf-python-rmq-app
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables for local RabbitMQ:**
   ```bash
   export RMQ_HOST=localhost
   export RMQ_PORT=5672
   export RMQ_USERNAME=guest
   export RMQ_PASSWORD=guest
   export RMQ_VHOST=/
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

The application will be available at `http://localhost:5000`

## Cloud Foundry Deployment

### Step 1: Set up CUPS Service

1. **Edit the CUPS setup script:**
   ```bash
   nano setup-cups.sh
   ```
   
   Update the following variables with your RabbitMQ credentials:
   ```bash
   RMQ_HOST="your-rabbitmq-host.com"
   RMQ_PORT="5672"
   RMQ_USERNAME="your-username"
   RMQ_PASSWORD="your-password"
   RMQ_VHOST="/"
   SERVICE_NAME="rabbitmq-service"
   ```

2. **Login to Cloud Foundry:**
   ```bash
   cf login -a <your-cf-api-endpoint>
   ```

3. **Run the CUPS setup script:**
   ```bash
   ./setup-cups.sh
   ```

### Step 2: Deploy the Application

1. **Push the application:**
   ```bash
   cf push
   ```

The application will automatically bind to the `rabbitmq-service` CUPS service as specified in `manifest.yml`.

## API Endpoints

### Health Check
```
GET /
```
Returns application health status and RabbitMQ connection status.

**Response:**
```json
{
    "status": "healthy",
    "service": "CF Python RMQ App",
    "rmq_connected": true
}
```

### Publish Message
```
POST /publish
```
Publishes a message to a RabbitMQ queue.

**Request Body:**
```json
{
    "queue": "my_queue",
    "message": {
        "text": "Hello, RabbitMQ!",
        "timestamp": "2024-01-01T00:00:00Z"
    }
}
```

**Response:**
```json
{
    "status": "success",
    "message": "Message published successfully",
    "queue": "my_queue"
}
```

### Queue Information
```
GET /queue/<queue_name>/info
```
Returns information about a specific queue.

**Response:**
```json
{
    "status": "success",
    "queue_info": {
        "queue": "my_queue",
        "message_count": 5,
        "consumer_count": 0
    }
}
```

### List Services
```
GET /services
```
Lists all bound Cloud Foundry services (useful for debugging).

**Response:**
```json
{
    "status": "success",
    "services": [
        {
            "name": "rabbitmq-service",
            "label": "user-provided",
            "plan": null,
            "tags": []
        }
    ]
}
```

## Configuration

### Environment Variables

The application supports the following environment variables for local development:

- `RMQ_HOST`: RabbitMQ hostname (default: localhost)
- `RMQ_PORT`: RabbitMQ port (default: 5672)
- `RMQ_USERNAME`: RabbitMQ username (default: guest)
- `RMQ_PASSWORD`: RabbitMQ password (default: guest)
- `RMQ_VHOST`: RabbitMQ virtual host (default: /)
- `PORT`: Application port (default: 5000)

### Cloud Foundry Service Binding

When deployed to Cloud Foundry, the application automatically detects bound services using the `cfenv` library. It looks for services with names containing "rabbitmq" or "rmq".

## Testing the Application

1. **Check health:**
   ```bash
   curl https://your-app.cfapps.io/
   ```

2. **Publish a test message:**
   ```bash
   curl -X POST https://your-app.cfapps.io/publish \
     -H "Content-Type: application/json" \
     -d '{
       "queue": "test_queue",
       "message": {
         "text": "Hello from Cloud Foundry!",
         "timestamp": "'$(date -Iseconds)'"
       }
     }'
   ```

3. **Check queue information:**
   ```bash
   curl https://your-app.cfapps.io/queue/test_queue/info
   ```

## Troubleshooting

### Common Issues

1. **RabbitMQ Connection Failed:**
   - Verify CUPS service credentials are correct
   - Check if RabbitMQ instance is accessible from Cloud Foundry
   - Ensure firewall rules allow connection

2. **Service Not Found:**
   - Verify CUPS service name matches manifest.yml
   - Check if service is properly bound: `cf services`

3. **Application Won't Start:**
   - Check logs: `cf logs cf-python-rmq-app --recent`
   - Verify all dependencies in requirements.txt

### Debugging Commands

```bash
# Check application status
cf app cf-python-rmq-app

# View recent logs
cf logs cf-python-rmq-app --recent

# Check bound services
cf services

# View service details
cf service rabbitmq-service

# SSH into application container
cf ssh cf-python-rmq-app
```

## Security Considerations

- Store RabbitMQ credentials securely
- Use HTTPS endpoints in production
- Consider using service keys for enhanced security
- Regularly rotate credentials
- Monitor application logs for security events

## License

This project is provided as-is for educational and development purposes.
