"""
Configuration Loader for CF Service Tester Framework
Handles loading and validation of YAML configuration files
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    type: str
    connection_type: str
    marketplace: Optional[Dict[str, Any]] = None
    cups: Optional[Dict[str, Any]] = None

@dataclass
class MessageQueueConfig:
    enabled: bool
    type: str = "rabbitmq"
    connection_type: str = "cups"
    marketplace: Optional[Dict[str, Any]] = None
    cups: Optional[Dict[str, Any]] = None

@dataclass
class CacheConfig:
    enabled: bool
    type: str = "redis"
    connection_type: str = "marketplace"
    marketplace: Optional[Dict[str, Any]] = None
    cups: Optional[Dict[str, Any]] = None

@dataclass
class AppConfig:
    name: str
    description: str
    port: int
    database: DatabaseConfig
    message_queue: MessageQueueConfig
    cache: CacheConfig
    features: Dict[str, bool]
    sample_data: Dict[str, Any]
    deployment: Dict[str, Any]

class ConfigLoader:
    """Loads and validates application configuration from YAML files"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._find_config_file()
        self._config_data = None
        
    def _find_config_file(self) -> str:
        """Find the configuration file in common locations"""
        possible_paths = [
            os.path.join(os.getcwd(), "config", "app_config.yaml"),
            os.path.join(os.getcwd(), "app_config.yaml"),
            os.path.join(os.path.dirname(__file__), "..", "config", "app_config.yaml"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
                
        raise FileNotFoundError("Configuration file not found. Please ensure app_config.yaml exists.")
    
    def load_config(self) -> AppConfig:
        """Load and parse the configuration file"""
        try:
            with open(self.config_path, 'r') as file:
                self._config_data = yaml.safe_load(file)
            
            logger.info(f"Loaded configuration from: {self.config_path}")
            return self._parse_config()
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise
    
    def _parse_config(self) -> AppConfig:
        """Parse the loaded configuration into structured objects"""
        data = self._config_data
        
        # Parse database configuration
        db_config = DatabaseConfig(
            type=data['database']['type'],
            connection_type=data['database']['connection_type'],
            marketplace=data['database'].get('marketplace'),
            cups=data['database'].get('cups')
        )
        
        # Parse message queue configuration
        mq_data = data.get('message_queue', {})
        mq_config = MessageQueueConfig(
            enabled=mq_data.get('enabled', False),
            type=mq_data.get('type', 'rabbitmq'),
            connection_type=mq_data.get('connection_type', 'cups'),
            marketplace=mq_data.get('marketplace'),
            cups=mq_data.get('cups')
        )
        
        # Parse cache configuration
        cache_data = data.get('cache', {})
        cache_config = CacheConfig(
            enabled=cache_data.get('enabled', False),
            type=cache_data.get('type', 'redis'),
            connection_type=cache_data.get('connection_type', 'marketplace'),
            marketplace=cache_data.get('marketplace'),
            cups=cache_data.get('cups')
        )
        
        return AppConfig(
            name=data['app']['name'],
            description=data['app']['description'],
            port=data['app']['port'],
            database=db_config,
            message_queue=mq_config,
            cache=cache_config,
            features=data.get('features', {}),
            sample_data=data.get('sample_data', {}),
            deployment=data.get('deployment', {})
        )
    
    def validate_config(self, config: AppConfig) -> bool:
        """Validate the configuration for required fields and consistency"""
        errors = []
        
        # Validate database configuration
        if not config.database.type in ['postgres', 'mysql', 'inmemory']:
            errors.append(f"Invalid database type: {config.database.type}")
        
        if not config.database.connection_type in ['marketplace', 'cups']:
            errors.append(f"Invalid database connection type: {config.database.connection_type}")
        
        # Validate message queue if enabled
        if config.message_queue.enabled:
            if not config.message_queue.type in ['rabbitmq']:
                errors.append(f"Invalid message queue type: {config.message_queue.type}")
            
            if not config.message_queue.connection_type in ['marketplace', 'cups']:
                errors.append(f"Invalid message queue connection type: {config.message_queue.connection_type}")
        
        # Validate cache if enabled
        if config.cache.enabled:
            if not config.cache.type in ['redis', 'valkey']:
                errors.append(f"Invalid cache type: {config.cache.type}")
            
            if not config.cache.connection_type in ['marketplace', 'cups']:
                errors.append(f"Invalid cache connection type: {config.cache.connection_type}")
        
        # Validate feature dependencies
        if config.features.get('reservation_notifications') and not config.message_queue.enabled:
            errors.append("Feature 'reservation_notifications' requires message_queue to be enabled")
        
        if config.features.get('reservation_caching') and not config.cache.enabled:
            errors.append("Feature 'reservation_caching' requires cache to be enabled")
        
        if errors:
            for error in errors:
                logger.error(f"Configuration validation error: {error}")
            return False
        
        logger.info("Configuration validation passed")
        return True
    
    def get_service_bindings(self, config: AppConfig) -> Dict[str, str]:
        """Generate service binding names for CF manifest"""
        bindings = []
        
        # Database service
        if config.database.connection_type == 'marketplace':
            bindings.append(config.database.marketplace['instance_name'])
        else:
            bindings.append(config.database.cups['service_name'])
        
        # Message queue service
        if config.message_queue.enabled:
            if config.message_queue.connection_type == 'marketplace':
                bindings.append(config.message_queue.marketplace['instance_name'])
            else:
                bindings.append(config.message_queue.cups['service_name'])
        
        # Cache service
        if config.cache.enabled:
            if config.cache.connection_type == 'marketplace':
                bindings.append(config.cache.marketplace['instance_name'])
            else:
                bindings.append(config.cache.cups['service_name'])
        
        return bindings
