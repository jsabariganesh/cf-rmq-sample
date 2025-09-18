import os
import json
import logging
import ssl
import tempfile
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
        self._temp_cert_files = []
        self.connect()
    
    def connect(self):
        """Connect to RabbitMQ using CUPS service credentials with TLS support"""
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
                    'vhost': os.getenv('RMQ_VHOST', '/'),
                    'ssl_enabled': os.getenv('RMQ_SSL_ENABLED', 'false').lower() == 'true',
                    'ssl_verify': os.getenv('RMQ_SSL_VERIFY', 'true').lower() == 'true'
                }
                
                # For local development, support both file paths and content
                # File paths (legacy support)
                ca_cert_path = os.getenv('RMQ_CA_CERT_PATH')
                client_cert_path = os.getenv('RMQ_CLIENT_CERT_PATH')
                client_key_path = os.getenv('RMQ_CLIENT_KEY_PATH')
                
                # Certificate contents (preferred for CF)
                ca_cert_content = os.getenv('RMQ_CA_CERT_CONTENT')
                client_cert_content = os.getenv('RMQ_CLIENT_CERT_CONTENT')
                client_key_content = os.getenv('RMQ_CLIENT_KEY_CONTENT')
                
                # Add certificate data to credentials
                if ca_cert_content:
                    credentials['ca_cert_content'] = ca_cert_content
                elif ca_cert_path:
                    credentials['ca_cert_path'] = ca_cert_path
                    
                if client_cert_content:
                    credentials['client_cert_content'] = client_cert_content
                elif client_cert_path:
                    credentials['client_cert_path'] = client_cert_path
                    
                if client_key_content:
                    credentials['client_key_content'] = client_key_content
                elif client_key_path:
                    credentials['client_key_path'] = client_key_path
                logger.info("Using environment variables for RMQ connection")
            
            # Determine if SSL/TLS should be used
            ssl_enabled = credentials.get('ssl_enabled', False)
            ssl_options = None
            
            if ssl_enabled:
                ssl_options = self._create_ssl_context(credentials)
                if ssl_options:
                    logger.info("TLS/SSL enabled for RabbitMQ connection")
                else:
                    logger.warning("SSL enabled but failed to create SSL context, falling back to non-SSL")
            
            # Determine port based on SSL
            default_port = 5671 if ssl_enabled else 5672
            port = credentials.get('port', default_port)
            
            # Create connection parameters
            connection_params = pika.ConnectionParameters(
                host=credentials.get('hostname', credentials.get('host')),
                port=port,
                virtual_host=credentials.get('vhost', '/'),
                credentials=pika.PlainCredentials(
                    credentials.get('username'),
                    credentials.get('password')
                ),
                ssl_options=ssl_options,
                heartbeat=600,  # Add heartbeat to keep connection alive
                blocked_connection_timeout=300  # Add timeout for blocked connections
            )
            
            # Establish connection
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            connection_type = "TLS/SSL" if ssl_enabled else "non-SSL"
            logger.info(f"Successfully connected to RabbitMQ using {connection_type}")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            self.connection = None
            self.channel = None
    
    def _create_ssl_context(self, credentials):
        """Create SSL context for TLS connections"""
        temp_files = []
        
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Configure certificate verification
            if not credentials.get('ssl_verify', True):
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                logger.warning("SSL certificate verification disabled")
            
            # Handle CA certificate
            ca_cert_content = credentials.get('ca_cert_content')
            ca_cert_path = credentials.get('ca_cert_path')
            
            if ca_cert_content:
                # Create temporary file for CA certificate content
                ca_temp = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
                ca_temp.write(ca_cert_content.replace('\\n', '\n'))
                ca_temp.flush()
                ca_temp.close()
                temp_files.append(ca_temp.name)
                
                context.load_verify_locations(ca_temp.name)
                logger.info("Loaded CA certificate from service credentials")
                
            elif ca_cert_path and os.path.exists(ca_cert_path):
                context.load_verify_locations(ca_cert_path)
                logger.info(f"Loaded CA certificate from: {ca_cert_path}")
            
            # Handle client certificate and key
            client_cert_content = credentials.get('client_cert_content')
            client_key_content = credentials.get('client_key_content')
            client_cert_path = credentials.get('client_cert_path')
            client_key_path = credentials.get('client_key_path')
            
            if client_cert_content and client_key_content:
                # Create temporary files for client certificate and key
                cert_temp = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
                cert_temp.write(client_cert_content.replace('\\n', '\n'))
                cert_temp.flush()
                cert_temp.close()
                temp_files.append(cert_temp.name)
                
                key_temp = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
                key_temp.write(client_key_content.replace('\\n', '\n'))
                key_temp.flush()
                key_temp.close()
                temp_files.append(key_temp.name)
                
                context.load_cert_chain(cert_temp.name, key_temp.name)
                logger.info("Loaded client certificate from service credentials")
                
            elif client_cert_path and client_key_path:
                if os.path.exists(client_cert_path) and os.path.exists(client_key_path):
                    context.load_cert_chain(client_cert_path, client_key_path)
                    logger.info(f"Loaded client certificate from: {client_cert_path}")
                else:
                    logger.error("Client certificate or key file not found")
                    self._cleanup_temp_files(temp_files)
                    return None
            
            # Store temp files for later cleanup
            self._temp_cert_files.extend(temp_files)
            
            # Create SSL options for pika
            ssl_options = pika.SSLOptions(context)
            return ssl_options
            
        except Exception as e:
            logger.error(f"Failed to create SSL context: {str(e)}")
            self._cleanup_temp_files(temp_files)
            return None
    
    def _cleanup_temp_files(self, temp_files):
        """Clean up temporary certificate files"""
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {str(e)}")
    
    def _ensure_connection(self):
        """Ensure connection and channel are available"""
        if not self.connection or self.connection.is_closed:
            logger.info("Connection lost, reconnecting...")
            self.connect()
        
        if not self.channel or self.channel.is_closed:
            if self.connection and not self.connection.is_closed:
                try:
                    self.channel = self.connection.channel()
                    logger.info("Recreated channel")
                except Exception as e:
                    logger.error(f"Failed to create channel: {str(e)}")
                    self.connect()
    
    def publish_message(self, queue_name, message):
        """Publish a message to a queue"""
        try:
            self._ensure_connection()
            
            if self.channel and not self.channel.is_closed:
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
            self._ensure_connection()
            
            if self.channel and not self.channel.is_closed:
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
            self._ensure_connection()
            
            if self.channel and not self.channel.is_closed:
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
        finally:
            # Clean up temporary certificate files
            if self._temp_cert_files:
                self._cleanup_temp_files(self._temp_cert_files)
                self._temp_cert_files = []

# Initialize RMQ connection
rmq = RMQConnection()

@app.route('/')
def health_check():
    """Health check endpoint"""
    # Check if connection is active
    connection_active = (rmq.connection is not None and 
                        not rmq.connection.is_closed and
                        rmq.channel is not None and 
                        not rmq.channel.is_closed)
    
    # Check if TLS is enabled
    ssl_enabled = os.getenv('RMQ_SSL_ENABLED', 'false').lower() == 'true'
    
    return jsonify({
        'status': 'healthy',
        'service': 'CF Python RMQ App',
        'rmq_connected': connection_active,
        'ssl_enabled': ssl_enabled,
        'ssl_port': 5671 if ssl_enabled else None
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

@app.route('/tls-config')
def tls_config():
    """Show TLS configuration status"""
    try:
        # Check CF service credentials first
        env = AppEnv()
        rmq_service = None
        for service in env.services:
            if 'rabbitmq' in service.name.lower() or 'rmq' in service.name.lower():
                rmq_service = service
                break
        
        if rmq_service:
            credentials = rmq_service.credentials
            source = "cf_service"
        else:
            # Use environment variables
            credentials = {
                'ssl_enabled': os.getenv('RMQ_SSL_ENABLED', 'false').lower() == 'true',
                'ssl_verify': os.getenv('RMQ_SSL_VERIFY', 'true').lower() == 'true',
                'ca_cert_path': os.getenv('RMQ_CA_CERT_PATH'),
                'client_cert_path': os.getenv('RMQ_CLIENT_CERT_PATH'),
                'client_key_path': os.getenv('RMQ_CLIENT_KEY_PATH'),
                'ca_cert_content': os.getenv('RMQ_CA_CERT_CONTENT'),
                'client_cert_content': os.getenv('RMQ_CLIENT_CERT_CONTENT'),
                'client_key_content': os.getenv('RMQ_CLIENT_KEY_CONTENT')
            }
            source = "environment"
        
        ssl_enabled = credentials.get('ssl_enabled', False)
        ssl_verify = credentials.get('ssl_verify', True)
        
        # Check certificate configuration
        ca_cert_content = credentials.get('ca_cert_content')
        client_cert_content = credentials.get('client_cert_content')
        client_key_content = credentials.get('client_key_content')
        ca_cert_path = credentials.get('ca_cert_path')
        client_cert_path = credentials.get('client_cert_path')
        client_key_path = credentials.get('client_key_path')
        
        config = {
            'ssl_enabled': ssl_enabled,
            'ssl_verify': ssl_verify,
            'configuration_source': source,
            'ca_cert_configured': bool(ca_cert_content or ca_cert_path),
            'ca_cert_from_content': bool(ca_cert_content),
            'ca_cert_from_file': bool(ca_cert_path and os.path.exists(ca_cert_path)),
            'client_cert_configured': bool(client_cert_content or client_cert_path),
            'client_cert_from_content': bool(client_cert_content),
            'client_cert_from_file': bool(client_cert_path and os.path.exists(client_cert_path)),
            'client_key_configured': bool(client_key_content or client_key_path),
            'client_key_from_content': bool(client_key_content),
            'client_key_from_file': bool(client_key_path and os.path.exists(client_key_path)),
            'ssl_port': 5671 if ssl_enabled else None,
            'regular_port': 5672
        }
        
        # Add file paths (but not expose sensitive content)
        if ca_cert_path:
            config['ca_cert_path'] = ca_cert_path
        if client_cert_path:
            config['client_cert_path'] = client_cert_path
        if client_key_path:
            config['client_key_path'] = client_key_path
            
        # Add content indicators (but not the actual content)
        if ca_cert_content:
            config['ca_cert_content_length'] = len(ca_cert_content)
        if client_cert_content:
            config['client_cert_content_length'] = len(client_cert_content)
        if client_key_content:
            config['client_key_content_length'] = len(client_key_content)
        
        return jsonify({
            'status': 'success',
            'tls_config': config
        })
        
    except Exception as e:
        logger.error(f"Error getting TLS config: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Only close connection on actual app shutdown, not per request
import atexit
atexit.register(lambda: rmq.close())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)