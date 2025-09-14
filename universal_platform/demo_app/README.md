# Universal Platform Demo Application

A comprehensive enterprise demo application showcasing the Universal Platform's capabilities across multiple business domains.

## Features

### 🏢 Multi-Domain Architecture
- **E-commerce Platform**: Complete product catalog, order processing, payment handling
- **Healthcare System**: Patient management, appointment scheduling, medical records
- **Logistics Platform**: Shipment tracking, inventory management, delivery coordination

### 🔌 Plugin System
- **Hot-Loading**: Plugins can be loaded, unloaded, and reloaded without restarting
- **Domain-Specific**: Specialized plugins for each business domain
- **Cross-Domain**: Analytics and notification plugins that work across all domains

### 🏗️ Advanced Features
- **Multi-Tenant Support**: Complete tenant isolation and resource management
- **Event-Driven Architecture**: Real-time communication between domains
- **Advanced Dependency Injection**: Enterprise-grade DI with multiple scopes
- **Configuration Hot-Reloading**: Update settings without restart
- **Comprehensive Monitoring**: Health checks, metrics, and performance tracking
- **Admin Dashboard**: Real-time system management and monitoring

## Quick Start

### Prerequisites
- Python 3.11+
- Docker and Docker Compose (optional)

### Local Development

1. **Clone and Setup**
   ```bash
   cd universal_platform/demo_app
   pip install -r requirements.txt
   ```

2. **Run the Application**
   ```bash
   python main.py
   ```

3. **Access the Application**
   - Main API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Admin Dashboard: http://localhost:8000/admin
   - System Health: http://localhost:8000/health
   - Metrics: http://localhost:8000/metrics

### Docker Deployment

1. **Build and Run**
   ```bash
   cd docker
   docker-compose up -d
   ```

2. **Access Services**
   - Application: http://localhost:8000
   - Grafana Dashboard: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090
   - Redis: localhost:6379
   - PostgreSQL: localhost:5432

## API Endpoints

### Core Platform
- `GET /` - Platform information
- `GET /health` - Health check
- `GET /status` - System status
- `GET /metrics` - Prometheus metrics

### E-commerce Domain (`/api/v1/ecommerce`)
- **Products**: `/products` - CRUD operations, inventory management
- **Customers**: `/customers` - Customer management and loyalty
- **Orders**: `/orders` - Order processing and fulfillment
- **Payments**: `/payments` - Payment processing and tracking

### Healthcare Domain (`/api/v1/healthcare`)
- **Patients**: `/patients` - Patient management
- **Appointments**: `/appointments` - Scheduling and management
- **Records**: `/records` - Medical records (HIPAA-compliant design)
- **Providers**: `/providers` - Healthcare provider management

### Logistics Domain (`/api/v1/logistics`)
- **Shipments**: `/shipments` - Shipment tracking and management
- **Warehouses**: `/warehouses` - Warehouse operations
- **Inventory**: `/inventory` - Cross-domain inventory tracking
- **Deliveries**: `/deliveries` - Delivery scheduling and tracking

### Administration (`/admin`)
- **Overview**: `/overview` - System overview and statistics
- **Plugins**: `/plugins` - Plugin management and hot-reloading
- **Tenants**: `/tenants` - Multi-tenant management
- **Health**: `/health` - Detailed health monitoring
- **Metrics**: `/metrics` - Performance metrics and analytics

## Domain Integration Examples

### Cross-Domain Workflows

1. **E-commerce to Logistics Integration**
   ```
   Order Created → Fulfillment Request → Shipment Created → Tracking Updated → Delivery Completed
   ```

2. **Healthcare to Logistics Integration**
   ```
   Medical Supply Order → Priority Fulfillment → Expedited Delivery → Supply Received
   ```

3. **Multi-Domain Analytics**
   ```
   All Domain Events → Analytics Plugin → Reports & Insights → Admin Dashboard
   ```

### Event-Driven Communication

The platform uses a comprehensive event system for real-time cross-domain communication:

```python
# E-commerce publishes order event
await event_bus.publish("ecommerce.order.created", order_data)

# Logistics subscribes and processes
await event_bus.subscribe("ecommerce.order.created", handle_fulfillment)

# Analytics tracks everything
await event_bus.subscribe("*", track_all_events)
```

## Plugin Development

### Creating a Plugin

```python
from universal_platform.core.plugins import PluginInterface, plugin_metadata

@plugin_metadata(
    name="my_plugin",
    version="1.0.0",
    description="My custom plugin"
)
class MyPlugin(PluginInterface):
    async def initialize(self, context=None):
        # Plugin initialization
        pass
    
    async def start(self):
        # Plugin startup
        pass
```

### Hot-Loading Plugins

```bash
# Via API
curl -X POST http://localhost:8000/admin/plugins/my_plugin/reload

# Via Admin Dashboard
http://localhost:8000/admin/plugins
```

## Configuration

### Environment-Specific Configuration

The application supports multiple configuration sources:

- **JSON Files**: `configurations/config.json`
- **Environment Variables**: Override any JSON setting
- **Runtime Updates**: Hot-reload via API

### Key Configuration Areas

```json
{
  "domains": {
    "ecommerce": {
      "enabled": true,
      "features": { "payment_processing": true }
    }
  },
  "plugins": {
    "enable_hot_reload": true,
    "scan_directories": ["plugins"]
  },
  "tenants": {
    "enable_multi_tenancy": true,
    "resource_limits": { "max_users": 1000 }
  }
}
```

## Monitoring and Analytics

### Built-in Monitoring

- **Health Checks**: Comprehensive system health monitoring
- **Metrics Collection**: CPU, memory, disk, application metrics
- **Performance Tracking**: API response times, throughput
- **Plugin Monitoring**: Plugin health and performance

### Analytics Plugin

Tracks all system events and provides insights:

```bash
# Get analytics report
curl http://localhost:8000/admin/analytics/report?domain=ecommerce&hours=24
```

### Notification System

Cross-domain notification delivery:

- **Order Confirmations**: Customer notifications
- **Inventory Alerts**: Low stock warnings
- **System Alerts**: Critical system events
- **Delivery Updates**: Shipment tracking

## Testing

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: Cross-domain interaction testing
- **API Tests**: Endpoint functionality testing
- **Plugin Tests**: Plugin loading and functionality

## Performance

### Optimization Features

- **Async Architecture**: Non-blocking I/O operations
- **Event Batching**: Efficient event processing
- **Connection Pooling**: Database and service connections
- **Caching**: Multi-level caching strategy
- **Resource Monitoring**: Automatic resource management

### Benchmarks

- **API Response Time**: < 100ms average
- **Event Processing**: > 1000 events/second
- **Plugin Hot-Reload**: < 5 seconds
- **Memory Usage**: < 200MB base footprint

## Security

### Security Features

- **JWT Authentication**: Secure API access
- **Multi-Tenant Isolation**: Complete data separation
- **Input Validation**: Comprehensive request validation
- **Audit Logging**: Complete action tracking
- **Plugin Sandboxing**: Isolated plugin execution

### Authentication

```bash
# Login to get JWT token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Use token for API calls
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/ecommerce/products
```

## Production Deployment

### Docker Production Setup

```bash
# Production docker-compose
docker-compose -f docker/docker-compose.prod.yml up -d

# With SSL and load balancing
docker-compose -f docker/docker-compose.prod.yml \
               -f docker/docker-compose.ssl.yml up -d
```

### Environment Variables

```bash
# Required production settings
export ENVIRONMENT=production
export JWT_SECRET=your-secure-secret-key
export DATABASE_URL=postgresql://user:pass@host:port/db
export REDIS_URL=redis://host:port/db
```

### Scaling Considerations

- **Horizontal Scaling**: Multiple application instances
- **Database Scaling**: Read replicas and connection pooling
- **Cache Scaling**: Redis cluster for high availability
- **Load Balancing**: Nginx or cloud load balancer

## Troubleshooting

### Common Issues

1. **Plugin Loading Fails**
   ```bash
   # Check plugin logs
   curl http://localhost:8000/admin/plugins/plugin_name/logs
   
   # Reload plugin
   curl -X POST http://localhost:8000/admin/plugins/plugin_name/reload
   ```

2. **High Memory Usage**
   ```bash
   # Check metrics
   curl http://localhost:8000/admin/metrics
   
   # Monitor resource usage
   curl http://localhost:8000/health
   ```

3. **Event Processing Issues**
   ```bash
   # Check event bus status
   curl http://localhost:8000/admin/events/stats
   ```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py
```

## Contributing

### Development Setup

1. **Clone Repository**
2. **Create Virtual Environment**
3. **Install Dependencies**
4. **Run Tests**
5. **Submit Pull Request**

### Code Quality

```bash
# Format code
black .
isort .

# Type checking
mypy .

# Linting
flake8 .
```

## License

This demo application is part of the Universal Platform project and is intended for demonstration and educational purposes.

## Support

For questions and support:
- Check the API documentation at `/docs`
- Monitor system health at `/health`
- View admin dashboard at `/admin`
- Check logs and metrics for debugging