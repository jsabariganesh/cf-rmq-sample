#!/usr/bin/env python3
"""
CF Service Tester Deployment Script
Automates the creation of CF services and deployment based on configuration
"""

import os
import sys
import yaml
import json
import subprocess
import logging
from pathlib import Path

# Add framework to path
sys.path.append(str(Path(__file__).parent))
from framework.config_loader import ConfigLoader

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class CFDeployer:
    """Handles Cloud Foundry deployment and service creation"""
    
    def __init__(self, config_path=None):
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()
        
    def run_cf_command(self, command):
        """Run a CF CLI command and return the result"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"CF command failed: {command}")
            logger.error(f"Error: {e.stderr}")
            return None
    
    def check_cf_login(self):
        """Check if user is logged into CF"""
        result = self.run_cf_command("cf target")
        if result is None:
            logger.error("Not logged into Cloud Foundry. Please run 'cf login' first.")
            return False
        
        logger.info("CF target verified")
        return True
    
    def create_database_service(self):
        """Create database service based on configuration"""
        db_config = self.config.database
        
        if db_config.connection_type == 'marketplace':
            # Create marketplace service
            marketplace = db_config.marketplace
            command = f"cf create-service {marketplace['service_name']} {marketplace['plan']} {marketplace['instance_name']}"
            
            logger.info(f"Creating marketplace database service: {marketplace['instance_name']}")
            result = self.run_cf_command(command)
            
            if result is not None:
                logger.info(f"Database service created: {marketplace['instance_name']}")
                return marketplace['instance_name']
        
        else:  # CUPS
            cups = db_config.cups
            credentials = cups['credentials']
            
            # Create CUPS service
            credentials_json = json.dumps(credentials)
            command = f"cf create-user-provided-service {cups['service_name']} -p '{credentials_json}'"
            
            logger.info(f"Creating CUPS database service: {cups['service_name']}")
            result = self.run_cf_command(command)
            
            if result is not None:
                logger.info(f"Database CUPS service created: {cups['service_name']}")
                return cups['service_name']
        
        logger.error("Failed to create database service")
        return None
    
    def create_message_queue_service(self):
        """Create message queue service if enabled"""
        if not self.config.message_queue.enabled:
            return None
        
        mq_config = self.config.message_queue
        
        if mq_config.connection_type == 'marketplace':
            # Create marketplace service
            marketplace = mq_config.marketplace
            command = f"cf create-service {marketplace['service_name']} {marketplace['plan']} {marketplace['instance_name']}"
            
            logger.info(f"Creating marketplace MQ service: {marketplace['instance_name']}")
            result = self.run_cf_command(command)
            
            if result is not None:
                logger.info(f"MQ service created: {marketplace['instance_name']}")
                return marketplace['instance_name']
        
        else:  # CUPS
            cups = mq_config.cups
            service_name = cups['service_name']
            
            # Build credentials with TLS support
            credentials = {}
            
            # Add TLS certificate contents if configured
            tls_config = cups.get('tls', {})
            if tls_config.get('enabled'):
                credentials['ssl_enabled'] = True
                credentials['ssl_verify'] = tls_config.get('verify_certificates', True)
                
                # Read certificate files and embed content
                for cert_type, path_key in [
                    ('ca_cert_content', 'ca_cert_path'),
                    ('client_cert_content', 'client_cert_path'),
                    ('client_key_content', 'client_key_path')
                ]:
                    cert_path = tls_config.get(path_key)
                    if cert_path and os.path.exists(cert_path):
                        with open(cert_path, 'r') as f:
                            cert_content = f.read().replace('\n', '\\n')
                            credentials[cert_type] = cert_content
                        logger.info(f"Embedded certificate: {cert_path}")
            
            # Create CUPS service
            credentials_json = json.dumps(credentials)
            command = f"cf create-user-provided-service {service_name} -p '{credentials_json}'"
            
            logger.info(f"Creating CUPS MQ service: {service_name}")
            result = self.run_cf_command(command)
            
            if result is not None:
                logger.info(f"MQ CUPS service created: {service_name}")
                return service_name
        
        logger.error("Failed to create message queue service")
        return None
    
    def create_cache_service(self):
        """Create cache service if enabled"""
        if not self.config.cache.enabled:
            return None
        
        cache_config = self.config.cache
        
        if cache_config.connection_type == 'marketplace':
            # Create marketplace service
            marketplace = cache_config.marketplace
            command = f"cf create-service {marketplace['service_name']} {marketplace['plan']} {marketplace['instance_name']}"
            
            logger.info(f"Creating marketplace cache service: {marketplace['instance_name']}")
            result = self.run_cf_command(command)
            
            if result is not None:
                logger.info(f"Cache service created: {marketplace['instance_name']}")
                return marketplace['instance_name']
        
        else:  # CUPS
            cups = cache_config.cups
            credentials = cups['credentials']
            
            # Create CUPS service
            credentials_json = json.dumps(credentials)
            command = f"cf create-user-provided-service {cups['service_name']} -p '{credentials_json}'"
            
            logger.info(f"Creating CUPS cache service: {cups['service_name']}")
            result = self.run_cf_command(command)
            
            if result is not None:
                logger.info(f"Cache CUPS service created: {cups['service_name']}")
                return cups['service_name']
        
        logger.error("Failed to create cache service")
        return None
    
    def update_manifest(self, service_names):
        """Update manifest.yml with service bindings"""
        manifest_path = Path(__file__).parent / "manifest.yml"
        
        try:
            with open(manifest_path, 'r') as f:
                manifest = yaml.safe_load(f)
            
            # Update service bindings
            if service_names:
                manifest['applications'][0]['services'] = service_names
            
            # Update app configuration from config
            app_config = manifest['applications'][0]
            app_config['name'] = self.config.name
            app_config['memory'] = self.config.deployment.get('memory', '512M')
            app_config['instances'] = self.config.deployment.get('instances', 1)
            
            # Write updated manifest
            with open(manifest_path, 'w') as f:
                yaml.dump(manifest, f, default_flow_style=False)
            
            logger.info(f"Updated manifest.yml with {len(service_names)} services")
            
        except Exception as e:
            logger.error(f"Failed to update manifest: {str(e)}")
    
    def deploy_app(self):
        """Deploy the application to CF"""
        logger.info("Deploying application to Cloud Foundry...")
        
        # Push the app
        result = self.run_cf_command("cf push")
        
        if result is not None:
            logger.info("Application deployed successfully!")
            
            # Get app info
            app_info = self.run_cf_command(f"cf app {self.config.name}")
            if app_info:
                logger.info("Application information:")
                print(app_info)
            
            return True
        else:
            logger.error("Application deployment failed")
            return False
    
    def deploy(self):
        """Full deployment process"""
        logger.info(f"Starting deployment of {self.config.name}")
        
        # Check CF login
        if not self.check_cf_login():
            return False
        
        # Create services
        service_names = []
        
        # Database service (required)
        db_service = self.create_database_service()
        if db_service:
            service_names.append(db_service)
        else:
            logger.error("Database service creation failed - aborting deployment")
            return False
        
        # Message queue service (optional)
        mq_service = self.create_message_queue_service()
        if mq_service:
            service_names.append(mq_service)
        
        # Cache service (optional)
        cache_service = self.create_cache_service()
        if cache_service:
            service_names.append(cache_service)
        
        # Update manifest
        self.update_manifest(service_names)
        
        # Deploy app
        success = self.deploy_app()
        
        if success:
            logger.info("🎉 Deployment completed successfully!")
            logger.info(f"Access your app at: https://{self.config.name}.cfapps.io/ui")
        else:
            logger.error("❌ Deployment failed")
        
        return success

def main():
    """Main deployment function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy CF Service Tester')
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deployed without actually deploying')
    
    args = parser.parse_args()
    
    try:
        deployer = CFDeployer(args.config)
        
        if args.dry_run:
            logger.info("DRY RUN - Configuration Summary:")
            logger.info(f"App Name: {deployer.config.name}")
            logger.info(f"Database: {deployer.config.database.type} ({deployer.config.database.connection_type})")
            logger.info(f"Message Queue: {'Enabled' if deployer.config.message_queue.enabled else 'Disabled'}")
            logger.info(f"Cache: {'Enabled' if deployer.config.cache.enabled else 'Disabled'}")
            logger.info("Use --deploy to actually deploy")
        else:
            success = deployer.deploy()
            sys.exit(0 if success else 1)
    
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
