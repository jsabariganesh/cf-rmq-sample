import os
import json
import logging
from flask import Flask, jsonify, request
import pika
from cfenv import AppEnv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class RMQConnection:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.connect()
    
    def connect(self):
        """Connect to RabbitMQ using CUPS service credentials"""
        try:
            # Get Cloud Foundry environment
            env = AppEnv()
            
            # Look for RMQ service (CUPS service name should be 'rabbitmq' or similar)
            rmq_service = None
            for service in env.services:
                if 'rabbitmq' in service.name.lower() or 'rmq' in service.name.lower():
                    rmq_service = service
                    break
            
            if rmq_service:
                credentials = rmq_service.credentials
                logger.info(f"Found RMQ service: {rmq_service.name}")
            else:
                # Fallback to environment variables for local development
                credentials = {
                    'hostname': os.getenv('RMQ_HOST', 'localhost'),
                    'port': int(os.getenv('RMQ_PORT', 5672)),
                    'username': os.getenv('RMQ_USERNAME', 'guest'),
                    'password': os.getenv('RMQ_PASSWORD', 'guest'),
                    'vhost': os.getenv('RMQ_VHOST', '/')
                }
                logger.info("Using environment variables for RMQ connection")
            
            # Create connection parameters
            connection_params = pika.ConnectionParameters(
                host=credentials.get('hostname', credentials.get('host')),
                port=credentials.get('port', 5672),
                virtual_host=credentials.get('vhost', '/'),
                credentials=pika.PlainCredentials(
                    credentials.get('username'),
                    credentials.get('password')
                )
            )
            
            # Establish connection
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            logger.info("Successfully connected to RabbitMQ")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            self.connection = None
            self.channel = None
    
    def publish_message(self, queue_name, message):
        """Publish a message to a queue"""
        try:
            if not self.channel:
                self.connect()
            
            if self.channel:
                # Declare queue (create if doesn't exist)
                self.channel.queue_declare(queue=queue_name, durable=True)
                
                # Publish message
                self.channel.basic_publish(
                    exchange='',
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Make message persistent
                    )
                )
                logger.info(f"Message published to queue '{queue_name}': {message}")
                return True
            else:
                logger.error("No RMQ channel available")
                return False
                
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            return False
    
    def consume_messages(self, queue_name, callback, auto_ack=True):
        """Consume messages from a queue"""
        try:
            if not self.channel:
                self.connect()
            
            if self.channel:
                # Declare queue
                self.channel.queue_declare(queue=queue_name, durable=True)
                
                # Set up consumer
                self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=callback,
                    auto_ack=auto_ack
                )
                
                logger.info(f"Starting to consume messages from queue '{queue_name}'")
                self.channel.start_consuming()
                
        except Exception as e:
            logger.error(f"Failed to consume messages: {str(e)}")
    
    def get_queue_info(self, queue_name):
        """Get information about a queue"""
        try:
            if not self.channel:
                self.connect()
            
            if self.channel:
                method = self.channel.queue_declare(queue=queue_name, passive=True)
                return {
                    'queue': queue_name,
                    'message_count': method.method.message_count,
                    'consumer_count': method.method.consumer_count
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get queue info: {str(e)}")
            return None
    
    def close(self):
        """Close the connection"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RMQ connection: {str(e)}")

# Initialize RMQ connection
rmq = RMQConnection()

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'CF Python RMQ App',
        'rmq_connected': rmq.connection is not None and not rmq.connection.is_closed
    })

@app.route('/publish', methods=['POST'])
def publish_message():
    """Publish a message to RabbitMQ"""
    try:
        data = request.get_json()
        queue_name = data.get('queue', 'default_queue')
        message = data.get('message', {})
        
        success = rmq.publish_message(queue_name, message)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Message published successfully',
                'queue': queue_name
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to publish message'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in publish endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/queue/<queue_name>/info')
def queue_info(queue_name):
    """Get information about a queue"""
    try:
        info = rmq.get_queue_info(queue_name)
        
        if info:
            return jsonify({
                'status': 'success',
                'queue_info': info
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to get queue information'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in queue info endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/services')
def list_services():
    """List all bound services (useful for debugging)"""
    try:
        env = AppEnv()
        services = []
        
        for service in env.services:
            services.append({
                'name': service.name,
                'label': service.label,
                'plan': service.plan,
                'tags': service.tags
            })
        
        return jsonify({
            'status': 'success',
            'services': services
        })
        
    except Exception as e:
        logger.error(f"Error listing services: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Cleanup on app shutdown
@app.teardown_appcontext
def close_rmq_connection(error):
    if rmq:
        rmq.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
