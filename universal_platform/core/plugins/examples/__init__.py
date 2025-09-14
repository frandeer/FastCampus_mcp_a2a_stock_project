"""
Universal Platform Plugin Examples

This package contains example plugins demonstrating various plugin types
and capabilities of the universal platform plugin system.

Example Plugins:
- EmailServicePlugin: Service-type plugin for email functionality
- DatabaseConnectorPlugin: Connector-type plugin for database connectivity  
- DataTransformerPlugin: Transformer-type plugin for data format conversion
- SystemMonitorPlugin: Monitor-type plugin for system metrics and alerting

Usage:
    from universal_platform.core.plugins.examples import EmailServicePlugin
    
    # Create and configure plugin
    plugin = EmailServicePlugin()
    config = PluginConfig(...)
    
    # Initialize and start
    await plugin.initialize(config)
    await plugin.start()
    
    # Use plugin functionality
    result = await plugin.process_request({...})
"""

from .email_service_plugin import EmailServicePlugin
from .database_connector_plugin import DatabaseConnectorPlugin
from .data_transformer_plugin import DataTransformerPlugin
from .system_monitor_plugin import SystemMonitorPlugin

__all__ = [
    'EmailServicePlugin',
    'DatabaseConnectorPlugin', 
    'DataTransformerPlugin',
    'SystemMonitorPlugin'
]

# Plugin registry for discovery
EXAMPLE_PLUGINS = {
    'email_service': EmailServicePlugin,
    'database_connector': DatabaseConnectorPlugin,
    'data_transformer': DataTransformerPlugin,
    'system_monitor': SystemMonitorPlugin
}

def get_example_plugin(plugin_name: str):
    """Get an example plugin class by name."""
    return EXAMPLE_PLUGINS.get(plugin_name)

def list_example_plugins():
    """List all available example plugins."""
    return list(EXAMPLE_PLUGINS.keys())