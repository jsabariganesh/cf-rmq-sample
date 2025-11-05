"""
Service Manager for CF Service Tester Framework
Handles connections to various CF services (Database, Message Queue, Cache)
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from cfenv import AppEnv

from .config_loader import AppConfig, DatabaseConfig, MessageQueueConfig, CacheConfig

logger = logging.getLogger(__name__)

class ServiceConnection(ABC):
    """Abstract base class for service connections"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection = None
        self.is_connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the service"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection to the service"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the service is healthy and accessible"""
        pass

class DatabaseConnection(ServiceConnection):
    """Database connection handler supporting PostgreSQL, MySQL, and in-memory"""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config.__dict__)
        self.db_type = config.type
        self.connection_type = config.connection_type
        self._setup_connection_params()
    
    def _setup_connection_params(self):
        """Setup connection parameters from CF services or environment"""
        try:
            env = AppEnv()
            
            if self.connection_type == 'marketplace':
                # Find marketplace service
                service_name = self.config['marketplace']['instance_name']
                service = self._find_service_by_name(env, service_name)
                if service:
                    self.connection_params = service.credentials
                    logger.info(f"Found marketplace database service: {service_name}")
                else:
                    raise Exception(f"Marketplace service not found: {service_name}")
            
            else:  # CUPS
                service_name = self.config['cups']['service_name']
                service = self._find_service_by_name(env, service_name)
                if service:
                    self.connection_params = service.credentials
                    logger.info(f"Found CUPS database service: {service_name}")
                else:
                    # Fallback to environment variables
                    self.connection_params = self.config['cups']['credentials']
                    logger.info("Using CUPS credentials from config")
        
        except Exception as e:
            logger.warning(f"CF service discovery failed, using fallback: {str(e)}")
            # Use in-memory database as fallback
            self.db_type = 'inmemory'
            self.connection_params = {}
    
    def _find_service_by_name(self, env: AppEnv, service_name: str):
        """Find a service by name in CF environment"""
        for service in env.services:
            if service.name == service_name:
                return service
        return None
    
    def connect(self) -> bool:
        """Establish database connection based on type"""
        try:
            if self.db_type == 'postgres':
                return self._connect_postgres()
            elif self.db_type == 'mysql':
                return self._connect_mysql()
            elif self.db_type == 'inmemory':
                return self._connect_inmemory()
            else:
                raise Exception(f"Unsupported database type: {self.db_type}")
        
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return False
    
    def _connect_postgres(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            self.connection = psycopg2.connect(
                host=self.connection_params.get('hostname', self.connection_params.get('host')),
                port=self.connection_params.get('port', 5432),
                database=self.connection_params.get('database', self.connection_params.get('name')),
                user=self.connection_params.get('username', self.connection_params.get('user')),
                password=self.connection_params.get('password'),
                cursor_factory=RealDictCursor
            )
            self.is_connected = True
            logger.info("Connected to PostgreSQL database")
            return True
        
        except ImportError:
            logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
            return False
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {str(e)}")
            return False
    
    def _connect_mysql(self) -> bool:
        """Connect to MySQL database"""
        try:
            import pymysql
            
            self.connection = pymysql.connect(
                host=self.connection_params.get('hostname', self.connection_params.get('host')),
                port=self.connection_params.get('port', 3306),
                database=self.connection_params.get('database', self.connection_params.get('name')),
                user=self.connection_params.get('username', self.connection_params.get('user')),
                password=self.connection_params.get('password'),
                cursorclass=pymysql.cursors.DictCursor
            )
            self.is_connected = True
            logger.info("Connected to MySQL database")
            return True
        
        except ImportError:
            logger.error("PyMySQL not installed. Install with: pip install pymysql")
            return False
        except Exception as e:
            logger.error(f"MySQL connection failed: {str(e)}")
            return False
    
    def _connect_inmemory(self) -> bool:
        """Connect to in-memory SQLite database"""
        try:
            import sqlite3
            
            self.connection = sqlite3.connect(':memory:')
            self.connection.row_factory = sqlite3.Row
            self.is_connected = True
            logger.info("Connected to in-memory SQLite database")
            return True
        
        except Exception as e:
            logger.error(f"In-memory database connection failed: {str(e)}")
            return False
    
    def disconnect(self) -> bool:
        """Close database connection"""
        try:
            if self.connection:
                self.connection.close()
                self.is_connected = False
                logger.info("Database connection closed")
            return True
        except Exception as e:
            logger.error(f"Error closing database connection: {str(e)}")
            return False
    
    def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            if not self.connection:
                return False
            
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True
        
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a query and return results"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params or ())
            
            if query.strip().upper().startswith('SELECT'):
                if self.db_type == 'inmemory':
                    return [dict(row) for row in cursor.fetchall()]
                else:
                    return cursor.fetchall()
            else:
                self.connection.commit()
                return []
        
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            self.connection.rollback()
            raise

class MessageQueueConnection(ServiceConnection):
    """Message Queue connection handler (RabbitMQ)"""
    
    def __init__(self, config: MessageQueueConfig):
        super().__init__(config.__dict__)
        self.mq_type = config.type
        self.connection_type = config.connection_type
        self.channel = None
        self._setup_connection_params()
    
    def _setup_connection_params(self):
        """Setup MQ connection parameters"""
        try:
            env = AppEnv()
            
            if self.connection_type == 'marketplace':
                service_name = self.config['marketplace']['instance_name']
                service = self._find_service_by_name(env, service_name)
                if service:
                    self.connection_params = service.credentials
                    logger.info(f"Found marketplace MQ service: {service_name}")
            else:  # CUPS
                service_name = self.config['cups']['service_name']
                service = self._find_service_by_name(env, service_name)
                if service:
                    self.connection_params = service.credentials
                    logger.info(f"Found CUPS MQ service: {service_name}")
        
        except Exception as e:
            logger.warning(f"MQ service discovery failed: {str(e)}")
            self.connection_params = {}
    
    def _find_service_by_name(self, env: AppEnv, service_name: str):
        """Find a service by name in CF environment"""
        for service in env.services:
            if service.name == service_name:
                return service
        return None
    
    def connect(self) -> bool:
        """Connect to RabbitMQ"""
        try:
            import pika
            import ssl
            import tempfile
            
            # Setup connection parameters
            host = self.connection_params.get('hostname', self.connection_params.get('host', 'localhost'))
            port = self.connection_params.get('port', 5672)
            username = self.connection_params.get('username', 'guest')
            password = self.connection_params.get('password', 'guest')
            vhost = self.connection_params.get('vhost', '/')
            
            # SSL configuration
            ssl_enabled = self.connection_params.get('ssl_enabled', False)
            ssl_options = None
            
            if ssl_enabled:
                ssl_options = self._create_ssl_context()
                port = port if port != 5672 else 5671  # Default TLS port
            
            connection_params = pika.ConnectionParameters(
                host=host,
                port=port,
                virtual_host=vhost,
                credentials=pika.PlainCredentials(username, password),
                ssl_options=ssl_options,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            self.is_connected = True
            
            connection_type = "TLS/SSL" if ssl_enabled else "non-SSL"
            logger.info(f"Connected to RabbitMQ using {connection_type}")
            return True
        
        except ImportError:
            logger.error("pika not installed. Install with: pip install pika")
            return False
        except Exception as e:
            logger.error(f"RabbitMQ connection failed: {str(e)}")
            return False
    
    def _create_ssl_context(self):
        """Create SSL context for TLS connections"""
        try:
            import ssl
            import tempfile
            
            context = ssl.create_default_context()
            
            # Configure certificate verification
            tls_config = self.config.get('cups', {}).get('tls', {})
            if not tls_config.get('verify_certificates', True):
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            
            # Handle certificate content from service credentials
            ca_cert_content = self.connection_params.get('ca_cert_content')
            if ca_cert_content:
                ca_temp = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
                ca_temp.write(ca_cert_content.replace('\\n', '\n'))
                ca_temp.close()
                context.load_verify_locations(ca_temp.name)
            
            return pika.SSLOptions(context)
        
        except Exception as e:
            logger.error(f"SSL context creation failed: {str(e)}")
            return None
    
    def disconnect(self) -> bool:
        """Close RabbitMQ connection"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                self.is_connected = False
                logger.info("RabbitMQ connection closed")
            return True
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {str(e)}")
            return False
    
    def health_check(self) -> bool:
        """Check RabbitMQ connectivity"""
        try:
            return (self.connection and not self.connection.is_closed and 
                   self.channel and not self.channel.is_closed)
        except Exception:
            return False
    
    def publish_message(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Publish a message to a queue"""
        try:
            import json
            
            if not self.channel or self.channel.is_closed:
                return False
            
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            return True
        
        except Exception as e:
            logger.error(f"Message publishing failed: {str(e)}")
            return False

class CacheConnection(ServiceConnection):
    """Cache connection handler (Redis/Valkey)"""
    
    def __init__(self, config: CacheConfig):
        super().__init__(config.__dict__)
        self.cache_type = config.type
        self.connection_type = config.connection_type
        self._setup_connection_params()
    
    def _setup_connection_params(self):
        """Setup cache connection parameters"""
        try:
            env = AppEnv()
            
            if self.connection_type == 'marketplace':
                service_name = self.config['marketplace']['instance_name']
                service = self._find_service_by_name(env, service_name)
                if service:
                    self.connection_params = service.credentials
                    logger.info(f"Found marketplace cache service: {service_name}")
            else:  # CUPS
                service_name = self.config['cups']['service_name']
                service = self._find_service_by_name(env, service_name)
                if service:
                    self.connection_params = service.credentials
                    logger.info(f"Found CUPS cache service: {service_name}")
        
        except Exception as e:
            logger.warning(f"Cache service discovery failed: {str(e)}")
            self.connection_params = {}
    
    def _find_service_by_name(self, env: AppEnv, service_name: str):
        """Find a service by name in CF environment"""
        for service in env.services:
            if service.name == service_name:
                return service
        return None
    
    def connect(self) -> bool:
        """Connect to Redis/Valkey"""
        try:
            import redis
            
            host = self.connection_params.get('hostname', self.connection_params.get('host', 'localhost'))
            port = self.connection_params.get('port', 6379)
            password = self.connection_params.get('password')
            
            self.connection = redis.Redis(
                host=host,
                port=port,
                password=password,
                decode_responses=True
            )
            
            # Test connection
            self.connection.ping()
            self.is_connected = True
            logger.info(f"Connected to {self.cache_type} cache")
            return True
        
        except ImportError:
            logger.error("redis not installed. Install with: pip install redis")
            return False
        except Exception as e:
            logger.error(f"Cache connection failed: {str(e)}")
            return False
    
    def disconnect(self) -> bool:
        """Close cache connection"""
        try:
            if self.connection:
                self.connection.close()
                self.is_connected = False
                logger.info("Cache connection closed")
            return True
        except Exception as e:
            logger.error(f"Error closing cache connection: {str(e)}")
            return False
    
    def health_check(self) -> bool:
        """Check cache connectivity"""
        try:
            return self.connection.ping() if self.connection else False
        except Exception:
            return False
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        try:
            return self.connection.get(key) if self.connection else None
        except Exception as e:
            logger.error(f"Cache get failed: {str(e)}")
            return None
    
    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set value in cache"""
        try:
            return self.connection.setex(key, ttl, value) if self.connection else False
        except Exception as e:
            logger.error(f"Cache set failed: {str(e)}")
            return False

class ServiceManager:
    """Manages all service connections for the application"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.database = None
        self.message_queue = None
        self.cache = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize service connections based on configuration"""
        # Always initialize database
        self.database = DatabaseConnection(self.config.database)
        
        # Initialize message queue if enabled
        if self.config.message_queue.enabled:
            self.message_queue = MessageQueueConnection(self.config.message_queue)
        
        # Initialize cache if enabled
        if self.config.cache.enabled:
            self.cache = CacheConnection(self.config.cache)
    
    def connect_all(self) -> Dict[str, bool]:
        """Connect to all configured services"""
        results = {}
        
        # Connect to database
        results['database'] = self.database.connect()
        
        # Connect to message queue if enabled
        if self.message_queue:
            results['message_queue'] = self.message_queue.connect()
        
        # Connect to cache if enabled
        if self.cache:
            results['cache'] = self.cache.connect()
        
        return results
    
    def disconnect_all(self):
        """Disconnect from all services"""
        if self.database:
            self.database.disconnect()
        
        if self.message_queue:
            self.message_queue.disconnect()
        
        if self.cache:
            self.cache.disconnect()
    
    def health_check_all(self) -> Dict[str, bool]:
        """Check health of all services"""
        results = {}
        
        results['database'] = self.database.health_check() if self.database else False
        results['message_queue'] = self.message_queue.health_check() if self.message_queue else True
        results['cache'] = self.cache.health_check() if self.cache else True
        
        return results
