import os
import json
import logging
import ssl
import tempfile
from flask import Flask, jsonify, request, render_template_string
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
    
    def get_messages(self, queue_name, max_messages=10):
        """Get messages from a queue without consuming them permanently"""
        try:
            self._ensure_connection()
            
            if not self.channel or self.channel.is_closed:
                return []
            
            messages = []
            
            # Use basic_get to retrieve messages one by one
            for _ in range(max_messages):
                method, properties, body = self.channel.basic_get(queue=queue_name, auto_ack=False)
                
                if method is None:
                    # No more messages
                    break
                
                try:
                    # Try to decode as JSON
                    message_data = json.loads(body.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # If not JSON, store as plain text
                    message_data = body.decode('utf-8', errors='replace')
                
                message_info = {
                    'delivery_tag': method.delivery_tag,
                    'exchange': method.exchange,
                    'routing_key': method.routing_key,
                    'message_count': method.message_count,
                    'redelivered': method.redelivered,
                    'body': message_data,
                    'properties': {
                        'content_type': properties.content_type,
                        'delivery_mode': properties.delivery_mode,
                        'timestamp': properties.timestamp.isoformat() if properties.timestamp else None,
                        'message_id': properties.message_id,
                        'user_id': properties.user_id,
                        'app_id': properties.app_id
                    }
                }
                
                messages.append(message_info)
                
                # Reject the message to put it back in the queue (nack with requeue=True)
                self.channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
            logger.info(f"Retrieved {len(messages)} messages from queue '{queue_name}'")
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get messages from queue '{queue_name}': {str(e)}")
            return []
    
    def consume_message(self, queue_name, count=1):
        """Consume (permanently remove) messages from a queue"""
        try:
            self._ensure_connection()
            
            if not self.channel or self.channel.is_closed:
                return []
            
            messages = []
            
            for _ in range(count):
                method, properties, body = self.channel.basic_get(queue=queue_name, auto_ack=True)
                
                if method is None:
                    break
                
                try:
                    message_data = json.loads(body.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    message_data = body.decode('utf-8', errors='replace')
                
                message_info = {
                    'exchange': method.exchange,
                    'routing_key': method.routing_key,
                    'body': message_data,
                    'consumed_at': json.dumps({'timestamp': 'now'})  # Add timestamp
                }
                
                messages.append(message_info)
            
            logger.info(f"Consumed {len(messages)} messages from queue '{queue_name}'")
            return messages
            
        except Exception as e:
            logger.error(f"Failed to consume messages from queue '{queue_name}': {str(e)}")
            return []
    
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

@app.route('/queue/<queue_name>/messages')
def get_queue_messages(queue_name):
    """Get messages from a queue (peek without consuming)"""
    try:
        max_messages = request.args.get('limit', 10, type=int)
        max_messages = min(max_messages, 50)  # Limit to 50 messages max
        
        messages = rmq.get_messages(queue_name, max_messages)
        
        return jsonify({
            'status': 'success',
            'queue': queue_name,
            'message_count': len(messages),
            'messages': messages
        })
        
    except Exception as e:
        logger.error(f"Error getting messages from queue '{queue_name}': {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/queue/<queue_name>/consume', methods=['POST'])
def consume_queue_messages(queue_name):
    """Consume (permanently remove) messages from a queue"""
    try:
        data = request.get_json() or {}
        count = data.get('count', 1)
        count = min(count, 10)  # Limit to 10 messages max per request
        
        messages = rmq.consume_message(queue_name, count)
        
        return jsonify({
            'status': 'success',
            'queue': queue_name,
            'consumed_count': len(messages),
            'messages': messages
        })
        
    except Exception as e:
        logger.error(f"Error consuming messages from queue '{queue_name}': {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/ui')
def web_ui():
    """Simple web UI for RabbitMQ management"""
    html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RabbitMQ Management UI</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #ff7b7b 0%, #ff416c 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .main-content {
            padding: 30px;
        }
        
        .section {
            margin-bottom: 40px;
            background: #f8f9fa;
            border-radius: 8px;
            padding: 25px;
            border-left: 4px solid #007bff;
        }
        
        .section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
        }
        
        .section h2::before {
            content: "📨";
            margin-right: 10px;
            font-size: 1.2em;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        
        input, textarea, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e1e5e9;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
        }
        
        textarea {
            height: 120px;
            resize: vertical;
            font-family: 'Courier New', monospace;
        }
        
        .btn {
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            margin-right: 10px;
            margin-bottom: 10px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
            color: #333;
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #bd2130 100%);
        }
        
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #ddd;
            background: #fff;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .result pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.4;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-success {
            background: #28a745;
        }
        
        .status-error {
            background: #dc3545;
        }
        
        .message-item {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 10px;
        }
        
        .message-header {
            font-weight: bold;
            color: #495057;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .message-body {
            background: #fff;
            padding: 10px;
            border-radius: 4px;
            border-left: 3px solid #007bff;
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .main-content {
                padding: 20px;
            }
        }
        
        .loading {
            display: none;
            color: #007bff;
            font-weight: 600;
        }
        
        .loading.show {
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐰 RabbitMQ Management</h1>
            <p>Send messages and manage queues with ease</p>
        </div>
        
        <div class="main-content">
            <div class="grid">
                <!-- Send Message Section -->
                <div class="section">
                    <h2>Send Message</h2>
                    <div class="form-group">
                        <label for="send-queue">Queue Name:</label>
                        <input type="text" id="send-queue" placeholder="e.g., my_queue" value="demo_queue">
                    </div>
                    <div class="form-group">
                        <label for="message-content">Message (JSON):</label>
                        <textarea id="message-content" placeholder='{"text": "Hello World!", "timestamp": "2025-01-01T00:00:00Z"}'>{"text": "Hello from UI!", "timestamp": "{{ current_time }}", "source": "web_ui"}</textarea>
                    </div>
                    <button class="btn" onclick="sendMessage()">Send Message</button>
                    <span class="loading" id="send-loading">Sending...</span>
                    <div class="result" id="send-result"></div>
                </div>
                
                <!-- Queue Info Section -->
                <div class="section">
                    <h2>Queue Information</h2>
                    <div class="form-group">
                        <label for="info-queue">Queue Name:</label>
                        <input type="text" id="info-queue" placeholder="e.g., my_queue" value="demo_queue">
                    </div>
                    <button class="btn btn-success" onclick="getQueueInfo()">Get Info</button>
                    <span class="loading" id="info-loading">Loading...</span>
                    <div class="result" id="info-result"></div>
                </div>
            </div>
            
            <!-- Read Messages Section -->
            <div class="section">
                <h2 style="border-left-color: #28a745;">📖 Read Messages</h2>
                <div class="grid">
                    <div>
                        <div class="form-group">
                            <label for="read-queue">Queue Name:</label>
                            <input type="text" id="read-queue" placeholder="e.g., my_queue" value="demo_queue">
                        </div>
                        <div class="form-group">
                            <label for="message-limit">Message Limit:</label>
                            <select id="message-limit">
                                <option value="5">5 messages</option>
                                <option value="10" selected>10 messages</option>
                                <option value="20">20 messages</option>
                                <option value="50">50 messages</option>
                            </select>
                        </div>
                    </div>
                    <div>
                        <div class="form-group">
                            <label for="consume-count">Consume Count:</label>
                            <select id="consume-count">
                                <option value="1" selected>1 message</option>
                                <option value="2">2 messages</option>
                                <option value="5">5 messages</option>
                                <option value="10">10 messages</option>
                            </select>
                        </div>
                    </div>
                </div>
                <button class="btn btn-warning" onclick="peekMessages()">👀 Peek Messages (Non-destructive)</button>
                <button class="btn btn-danger" onclick="consumeMessages()">🗑️ Consume Messages (Permanent)</button>
                <span class="loading" id="read-loading">Loading...</span>
                <div class="result" id="read-result"></div>
            </div>
            
            <!-- System Status -->
            <div class="section">
                <h2 style="border-left-color: #ffc107;">⚡ System Status</h2>
                <button class="btn btn-success" onclick="getSystemStatus()">Check Status</button>
                <button class="btn" onclick="getTlsConfig()">TLS Config</button>
                <span class="loading" id="status-loading">Loading...</span>
                <div class="result" id="status-result"></div>
            </div>
        </div>
    </div>

    <script>
        function showLoading(elementId, show = true) {
            const element = document.getElementById(elementId);
            if (show) {
                element.classList.add('show');
            } else {
                element.classList.remove('show');
            }
        }
        
        function displayResult(resultId, data, isError = false) {
            const resultDiv = document.getElementById(resultId);
            const statusClass = isError ? 'status-error' : 'status-success';
            const statusIcon = isError ? '❌' : '✅';
            
            resultDiv.innerHTML = `
                <div style="margin-bottom: 10px;">
                    <span class="status-indicator ${statusClass}"></span>
                    <strong>${statusIcon} ${isError ? 'Error' : 'Success'}</strong>
                </div>
                <pre>${JSON.stringify(data, null, 2)}</pre>
            `;
        }
        
        async function sendMessage() {
            showLoading('send-loading');
            try {
                const queue = document.getElementById('send-queue').value;
                const messageText = document.getElementById('message-content').value;
                
                if (!queue) {
                    throw new Error('Queue name is required');
                }
                
                let message;
                try {
                    message = JSON.parse(messageText);
                } catch (e) {
                    message = { text: messageText };
                }
                
                const response = await fetch('/publish', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        queue: queue,
                        message: message
                    })
                });
                
                const data = await response.json();
                displayResult('send-result', data, !response.ok);
                
            } catch (error) {
                displayResult('send-result', { error: error.message }, true);
            } finally {
                showLoading('send-loading', false);
            }
        }
        
        async function getQueueInfo() {
            showLoading('info-loading');
            try {
                const queue = document.getElementById('info-queue').value;
                if (!queue) {
                    throw new Error('Queue name is required');
                }
                
                const response = await fetch(`/queue/${encodeURIComponent(queue)}/info`);
                const data = await response.json();
                displayResult('info-result', data, !response.ok);
                
            } catch (error) {
                displayResult('info-result', { error: error.message }, true);
            } finally {
                showLoading('info-loading', false);
            }
        }
        
        async function peekMessages() {
            showLoading('read-loading');
            try {
                const queue = document.getElementById('read-queue').value;
                const limit = document.getElementById('message-limit').value;
                
                if (!queue) {
                    throw new Error('Queue name is required');
                }
                
                const response = await fetch(`/queue/${encodeURIComponent(queue)}/messages?limit=${limit}`);
                const data = await response.json();
                
                if (data.messages && data.messages.length > 0) {
                    displayMessagesFormatted('read-result', data);
                } else {
                    displayResult('read-result', data, !response.ok);
                }
                
            } catch (error) {
                displayResult('read-result', { error: error.message }, true);
            } finally {
                showLoading('read-loading', false);
            }
        }
        
        async function consumeMessages() {
            if (!confirm('This will permanently remove messages from the queue. Are you sure?')) {
                return;
            }
            
            showLoading('read-loading');
            try {
                const queue = document.getElementById('read-queue').value;
                const count = parseInt(document.getElementById('consume-count').value);
                
                if (!queue) {
                    throw new Error('Queue name is required');
                }
                
                const response = await fetch(`/queue/${encodeURIComponent(queue)}/consume`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ count: count })
                });
                
                const data = await response.json();
                
                if (data.messages && data.messages.length > 0) {
                    displayMessagesFormatted('read-result', data, true);
                } else {
                    displayResult('read-result', data, !response.ok);
                }
                
            } catch (error) {
                displayResult('read-result', { error: error.message }, true);
            } finally {
                showLoading('read-loading', false);
            }
        }
        
        function displayMessagesFormatted(resultId, data, consumed = false) {
            const resultDiv = document.getElementById(resultId);
            const action = consumed ? 'Consumed' : 'Peeked';
            const icon = consumed ? '🗑️' : '👀';
            
            let html = `
                <div style="margin-bottom: 15px;">
                    <span class="status-indicator status-success"></span>
                    <strong>${icon} ${action} ${data.messages.length} messages from "${data.queue}"</strong>
                </div>
            `;
            
            data.messages.forEach((msg, index) => {
                html += `
                    <div class="message-item">
                        <div class="message-header">
                            <span>Message #${index + 1}</span>
                            <small>${msg.redelivered ? '🔄 Redelivered' : '📩 New'}</small>
                        </div>
                        <div class="message-body">
                            ${JSON.stringify(msg.body, null, 2)}
                        </div>
                        ${!consumed ? `<small style="color: #6c757d; margin-top: 5px; display: block;">Delivery Tag: ${msg.delivery_tag} | Messages remaining: ${msg.message_count}</small>` : ''}
                    </div>
                `;
            });
            
            resultDiv.innerHTML = html;
        }
        
        async function getSystemStatus() {
            showLoading('status-loading');
            try {
                const response = await fetch('/');
                const data = await response.json();
                displayResult('status-result', data, !response.ok);
            } catch (error) {
                displayResult('status-result', { error: error.message }, true);
            } finally {
                showLoading('status-loading', false);
            }
        }
        
        async function getTlsConfig() {
            showLoading('status-loading');
            try {
                const response = await fetch('/tls-config');
                const data = await response.json();
                displayResult('status-result', data, !response.ok);
            } catch (error) {
                displayResult('status-result', { error: error.message }, true);
            } finally {
                showLoading('status-loading', false);
            }
        }
        
        // Auto-update timestamp in message template
        function updateTimestamp() {
            const messageContent = document.getElementById('message-content');
            const currentContent = messageContent.value;
            const now = new Date().toISOString();
            messageContent.value = currentContent.replace(/"timestamp":\s*"[^"]*"/, `"timestamp": "${now}"`);
        }
        
        // Update timestamp every 30 seconds
        setInterval(updateTimestamp, 30000);
        
        // Initial timestamp update
        updateTimestamp();
        
        // Load system status on page load
        window.addEventListener('load', () => {
            getSystemStatus();
        });
    </script>
</body>
</html>
    '''
    
    from datetime import datetime
    current_time = datetime.now().isoformat()
    return render_template_string(html_template, current_time=current_time)

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