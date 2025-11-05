# Cloud Foundry Service Tester Framework

A comprehensive framework for testing Cloud Foundry services through a practical ticket reservation system. This framework validates CF service connectivity, performance, and functionality using real CRUD operations.

## 🎯 Purpose

This framework is designed to **validate Cloud Foundry instances and service integrations**, not to be a production ticket system. It provides a simple, configurable way to test various CF services through a familiar application pattern.

## 🏗️ Architecture

### Framework Components
- **Configuration System**: YAML-based service configuration
- **Service Manager**: Abstracted service connections (Database, Message Queue, Cache)
- **Reservation Service**: CRUD operations with optional caching and notifications
- **Web UI**: Responsive interface for manual testing
- **Deployment Automation**: Automated CF service creation and app deployment

### Supported Services

#### Database (Required)
- **PostgreSQL** (via marketplace or CUPS)
- **MySQL** (via marketplace or CUPS)  
- **In-Memory SQLite** (fallback for testing)

#### Message Queue (Optional)
- **RabbitMQ** with full TLS support (via marketplace or CUPS)

#### Cache (Optional)
- **Redis** (via marketplace or CUPS)
- **Valkey** (via marketplace or CUPS)

## 🚀 Quick Start

### 1. Configuration

Edit `config/app_config.yaml` to match your CF environment:

```yaml
# Minimal configuration for PostgreSQL + RabbitMQ
app:
  name: "my-cf-test-app"
  description: "Testing CF services"
  port: 5000

database:
  type: "postgres"
  connection_type: "marketplace"  # or "cups"
  marketplace:
    service_name: "postgres"
    plan: "shared"
    instance_name: "test-db"

message_queue:
  enabled: true
  type: "rabbitmq"
  connection_type: "cups"
  cups:
    service_name: "rabbitmq-service"
    tls:
      enabled: true
      verify_certificates: false

cache:
  enabled: false  # Disable for minimal setup
```

### 2. Deploy to Cloud Foundry

```bash
# Automatic deployment (creates services + deploys app)
python deploy.py

# Or manual deployment
cf login
python deploy.py --dry-run  # Preview what will be created
python deploy.py           # Deploy
```

### 3. Access the Application

```bash
# Web UI
https://your-app.cfapps.io/ui

# API Health Check
curl https://your-app.cfapps.io/health

# Service Status
curl https://your-app.cfapps.io/services
```

## 📋 Configuration Reference

### Database Configuration

#### PostgreSQL (Marketplace)
```yaml
database:
  type: "postgres"
  connection_type: "marketplace"
  marketplace:
    service_name: "postgres"      # CF marketplace service name
    plan: "shared"                # Service plan
    instance_name: "my-db"        # Instance name to create
```

#### PostgreSQL (CUPS)
```yaml
database:
  type: "postgres"
  connection_type: "cups"
  cups:
    service_name: "postgres-cups"
    credentials:
      hostname: "db.example.com"
      port: 5432
      username: "dbuser"
      password: "dbpass"
      database: "reservations"
```

#### MySQL (Similar pattern)
```yaml
database:
  type: "mysql"
  connection_type: "marketplace"
  # ... similar to postgres
```

#### In-Memory (Testing)
```yaml
database:
  type: "inmemory"
  # No additional configuration needed
```

### Message Queue Configuration

#### RabbitMQ with TLS (CUPS)
```yaml
message_queue:
  enabled: true
  type: "rabbitmq"
  connection_type: "cups"
  cups:
    service_name: "rabbitmq-service"
    tls:
      enabled: true
      verify_certificates: true
      ca_cert_path: "./certs/ca-cert.pem"
      client_cert_path: "./certs/client-cert.pem"
      client_key_path: "./certs/client-key.pem"
```

#### RabbitMQ (Marketplace)
```yaml
message_queue:
  enabled: true
  type: "rabbitmq"
  connection_type: "marketplace"
  marketplace:
    service_name: "rabbitmq"
    plan: "standard"
    instance_name: "my-rmq"
```

### Cache Configuration

#### Redis (Marketplace)
```yaml
cache:
  enabled: true
  type: "redis"
  connection_type: "marketplace"
  marketplace:
    service_name: "redis"
    plan: "shared"
    instance_name: "my-cache"
```

#### Redis (CUPS)
```yaml
cache:
  enabled: true
  type: "redis"
  connection_type: "cups"
  cups:
    service_name: "redis-cups"
    credentials:
      hostname: "redis.example.com"
      port: 6379
      password: "redispass"
```

### Features Configuration

```yaml
features:
  reservation_notifications: true   # Requires message_queue.enabled
  reservation_caching: true        # Requires cache.enabled
  audit_logging: true
```

## 🔧 API Reference

### Health & Status
- `GET /health` - Application health check
- `GET /services` - Service connection status
- `GET /api/statistics` - Reservation statistics

### Reservations CRUD
- `GET /api/reservations` - List all reservations
- `GET /api/reservations/{id}` - Get specific reservation
- `POST /api/reservations` - Create new reservation
- `PUT /api/reservations/{id}` - Update reservation
- `DELETE /api/reservations/{id}` - Delete reservation

### Web Interface
- `GET /ui` - Web-based management interface

## 🧪 Testing Scenarios

### Basic Database Testing
1. **Connection Test**: Check `/health` endpoint
2. **CRUD Operations**: Create, read, update, delete reservations
3. **Data Persistence**: Restart app, verify data remains
4. **Concurrent Access**: Multiple users creating reservations

### Message Queue Testing
1. **Connection Test**: Enable MQ, check service status
2. **Message Publishing**: Create/update/delete reservations (triggers notifications)
3. **Queue Monitoring**: Use RabbitMQ management UI to see messages
4. **TLS Validation**: Test with/without certificate verification

### Cache Testing
1. **Connection Test**: Enable cache, check service status
2. **Cache Performance**: Load reservations multiple times, check response times
3. **Cache Invalidation**: Update reservation, verify cache clears
4. **Cache Fallback**: Disable cache, ensure app still works

### Service Failure Testing
1. **Database Failure**: Stop DB service, check app behavior
2. **Graceful Degradation**: Disable optional services, verify core functionality
3. **Recovery Testing**: Restart services, verify reconnection

## 🔍 Troubleshooting

### Common Issues

#### Database Connection Failed
```bash
# Check service binding
cf env your-app-name

# Check service status
cf service your-db-service

# Check logs
cf logs your-app-name --recent
```

#### Message Queue Connection Failed
```bash
# For CUPS services, check credentials
cf service rabbitmq-service

# For TLS issues, check certificate paths
# Verify certificates are embedded in service credentials
```

#### Cache Connection Failed
```bash
# Check Redis service
cf service your-cache-service

# Test connection manually
redis-cli -h hostname -p port -a password ping
```

### Debug Mode

Enable debug logging by setting environment variable:
```bash
cf set-env your-app-name FLASK_ENV development
cf restage your-app-name
```

### Service Binding Issues

List all services and their bindings:
```bash
cf services
cf service-keys your-service-name
```

## 🚀 Deployment Options

### Option 1: Automated Deployment
```bash
# Configure app_config.yaml first
python deploy.py
```

### Option 2: Manual Deployment
```bash
# 1. Create services manually
cf create-service postgres shared my-db
cf create-user-provided-service rabbitmq-service -p '{"credentials":"..."}'

# 2. Update manifest.yml with service names
# 3. Deploy app
cf push
```

### Option 3: Staged Deployment
```bash
# 1. Deploy with minimal services first
python deploy.py --config config/minimal.yaml

# 2. Add services incrementally
# 3. Test each addition
```

## 📊 Monitoring & Metrics

### Application Metrics
- Reservation count by status
- Recent activity (last 7 days)
- Service connection health
- Response times

### Service Metrics
- Database query performance
- Message queue throughput
- Cache hit/miss ratios
- Error rates

### CF Platform Metrics
- Memory usage
- CPU utilization
- Network connectivity
- Service availability

## 🔒 Security Considerations

### Database Security
- Use strong passwords
- Enable SSL/TLS for database connections
- Limit database user permissions

### Message Queue Security
- Enable TLS with certificate verification
- Use client certificates for authentication
- Secure queue permissions

### Application Security
- Input validation on all endpoints
- SQL injection prevention
- XSS protection in web UI

## 📚 Extension Points

### Adding New Database Types
1. Extend `DatabaseConnection` class in `service_manager.py`
2. Add connection logic for new database type
3. Update configuration schema

### Adding New Message Queue Types
1. Extend `MessageQueueConnection` class
2. Implement connection and messaging logic
3. Update configuration options

### Custom Business Logic
1. Extend `ReservationService` class
2. Add new endpoints in `app.py`
3. Update web UI as needed

## 🤝 Contributing

This framework is designed for CF service testing. When extending:

1. **Keep it simple**: Focus on service validation, not complex business logic
2. **Make it configurable**: All service connections should be configurable
3. **Test thoroughly**: Ensure all service combinations work
4. **Document changes**: Update configuration examples and documentation

## 📄 License

This framework is designed for Cloud Foundry service testing and validation purposes.
