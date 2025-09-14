"""
Configuration encryption and secrets management system.
"""

import os
import base64
import hashlib
import secrets
from typing import Dict, Any, Optional, Union, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import keyring
import hvac
from pathlib import Path
import json
import asyncio
import aiofiles
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption/decryption operations fail."""
    pass


class SecretsManager:
    """Base class for secrets management."""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_ttl: Dict[str, datetime] = {}
        self.default_ttl = timedelta(minutes=15)
        
    async def get_secret(self, key: str, use_cache: bool = True) -> Optional[str]:
        """Get a secret value."""
        if use_cache and key in self.cache:
            if datetime.now(timezone.utc) < self.cache_ttl.get(key, datetime.min.replace(tzinfo=timezone.utc)):
                return self.cache[key]
                
        value = await self._get_secret_impl(key)
        
        if use_cache and value is not None:
            self.cache[key] = value
            self.cache_ttl[key] = datetime.now(timezone.utc) + self.default_ttl
            
        return value
        
    async def set_secret(self, key: str, value: str) -> None:
        """Set a secret value."""
        await self._set_secret_impl(key, value)
        # Invalidate cache
        self.cache.pop(key, None)
        self.cache_ttl.pop(key, None)
        
    async def delete_secret(self, key: str) -> None:
        """Delete a secret."""
        await self._delete_secret_impl(key)
        # Invalidate cache
        self.cache.pop(key, None)
        self.cache_ttl.pop(key, None)
        
    def clear_cache(self):
        """Clear the secrets cache."""
        self.cache.clear()
        self.cache_ttl.clear()
        
    async def _get_secret_impl(self, key: str) -> Optional[str]:
        """Implementation-specific secret retrieval."""
        raise NotImplementedError
        
    async def _set_secret_impl(self, key: str, value: str) -> None:
        """Implementation-specific secret storage."""
        raise NotImplementedError
        
    async def _delete_secret_impl(self, key: str) -> None:
        """Implementation-specific secret deletion."""
        raise NotImplementedError


class FileSecretsManager(SecretsManager):
    """File-based secrets manager with encryption."""
    
    def __init__(self, secrets_file: Union[str, Path], encryption_key: bytes = None):
        super().__init__()
        self.secrets_file = Path(secrets_file)
        self.encryption_key = encryption_key or self._derive_key()
        self.fernet = Fernet(self.encryption_key)
        
    def _derive_key(self) -> bytes:
        """Derive encryption key from system information."""
        # This is a basic implementation - in production, use proper key management
        machine_id = hashlib.sha256(os.uname().machine.encode()).digest()[:32]
        return base64.urlsafe_b64encode(machine_id)
        
    async def _load_secrets(self) -> Dict[str, str]:
        """Load encrypted secrets from file."""
        if not self.secrets_file.exists():
            return {}
            
        try:
            async with aiofiles.open(self.secrets_file, 'rb') as f:
                encrypted_data = await f.read()
                
            if not encrypted_data:
                return {}
                
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
            
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
            return {}
            
    async def _save_secrets(self, secrets: Dict[str, str]) -> None:
        """Save encrypted secrets to file."""
        try:
            # Ensure parent directory exists
            self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = json.dumps(secrets).encode('utf-8')
            encrypted_data = self.fernet.encrypt(data)
            
            async with aiofiles.open(self.secrets_file, 'wb') as f:
                await f.write(encrypted_data)
                
            # Set restrictive permissions
            self.secrets_file.chmod(0o600)
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise EncryptionError(f"Failed to save secrets: {e}")
            
    async def _get_secret_impl(self, key: str) -> Optional[str]:
        """Get secret from encrypted file."""
        secrets = await self._load_secrets()
        return secrets.get(key)
        
    async def _set_secret_impl(self, key: str, value: str) -> None:
        """Set secret in encrypted file."""
        secrets = await self._load_secrets()
        secrets[key] = value
        await self._save_secrets(secrets)
        
    async def _delete_secret_impl(self, key: str) -> None:
        """Delete secret from encrypted file."""
        secrets = await self._load_secrets()
        secrets.pop(key, None)
        await self._save_secrets(secrets)


class KeyringSecretsManager(SecretsManager):
    """System keyring-based secrets manager."""
    
    def __init__(self, service_name: str = "universal_platform"):
        super().__init__()
        self.service_name = service_name
        
    async def _get_secret_impl(self, key: str) -> Optional[str]:
        """Get secret from system keyring."""
        try:
            return keyring.get_password(self.service_name, key)
        except Exception as e:
            logger.error(f"Failed to get secret from keyring: {e}")
            return None
            
    async def _set_secret_impl(self, key: str, value: str) -> None:
        """Set secret in system keyring."""
        try:
            keyring.set_password(self.service_name, key, value)
        except Exception as e:
            logger.error(f"Failed to set secret in keyring: {e}")
            raise EncryptionError(f"Failed to set secret in keyring: {e}")
            
    async def _delete_secret_impl(self, key: str) -> None:
        """Delete secret from system keyring."""
        try:
            keyring.delete_password(self.service_name, key)
        except Exception as e:
            logger.error(f"Failed to delete secret from keyring: {e}")
            raise EncryptionError(f"Failed to delete secret from keyring: {e}")


class VaultSecretsManager(SecretsManager):
    """HashiCorp Vault secrets manager."""
    
    def __init__(self, url: str, token: str = None, mount_point: str = "secret"):
        super().__init__()
        self.url = url
        self.mount_point = mount_point
        self.client = hvac.Client(url=url, token=token)
        
    async def _get_secret_impl(self, key: str) -> Optional[str]:
        """Get secret from Vault."""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=key, mount_point=self.mount_point
            )
            return response['data']['data'].get('value')
        except Exception as e:
            logger.error(f"Failed to get secret from Vault: {e}")
            return None
            
    async def _set_secret_impl(self, key: str, value: str) -> None:
        """Set secret in Vault."""
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=key,
                secret={'value': value},
                mount_point=self.mount_point
            )
        except Exception as e:
            logger.error(f"Failed to set secret in Vault: {e}")
            raise EncryptionError(f"Failed to set secret in Vault: {e}")
            
    async def _delete_secret_impl(self, key: str) -> None:
        """Delete secret from Vault."""
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=key, mount_point=self.mount_point
            )
        except Exception as e:
            logger.error(f"Failed to delete secret from Vault: {e}")
            raise EncryptionError(f"Failed to delete secret from Vault: {e}")


class ConfigEncryption:
    """Configuration encryption and decryption utilities."""
    
    def __init__(self, encryption_key: bytes = None):
        self.encryption_key = encryption_key or self._generate_key()
        self.fernet = Fernet(self.encryption_key)
        self.asymmetric_key = None
        
    @staticmethod
    def _generate_key() -> bytes:
        """Generate a new encryption key."""
        return Fernet.generate_key()
        
    def generate_asymmetric_key(self) -> None:
        """Generate asymmetric key pair for advanced encryption."""
        self.asymmetric_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
    def encrypt_value(self, value: str) -> str:
        """Encrypt a configuration value."""
        try:
            encrypted = self.fernet.encrypt(value.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt value: {e}")
            
    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a configuration value."""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode('utf-8'))
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt value: {e}")
            
    def encrypt_config(self, config: Dict[str, Any], 
                      sensitive_keys: List[str] = None) -> Dict[str, Any]:
        """Encrypt sensitive keys in configuration."""
        if sensitive_keys is None:
            sensitive_keys = self._detect_sensitive_keys(config)
            
        encrypted_config = config.copy()
        
        for key in sensitive_keys:
            if key in encrypted_config:
                value = encrypted_config[key]
                if isinstance(value, str):
                    encrypted_config[key] = {
                        "_encrypted": True,
                        "_value": self.encrypt_value(value)
                    }
                    
        return encrypted_config
        
    def decrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt encrypted keys in configuration."""
        decrypted_config = {}
        
        for key, value in config.items():
            if isinstance(value, dict) and value.get("_encrypted"):
                decrypted_config[key] = self.decrypt_value(value["_value"])
            elif isinstance(value, dict):
                decrypted_config[key] = self.decrypt_config(value)
            else:
                decrypted_config[key] = value
                
        return decrypted_config
        
    def _detect_sensitive_keys(self, config: Dict[str, Any]) -> List[str]:
        """Detect potentially sensitive configuration keys."""
        sensitive_patterns = [
            'password', 'passwd', 'secret', 'key', 'token', 'api_key',
            'private_key', 'credential', 'auth', 'cert', 'ssl'
        ]
        
        sensitive_keys = []
        for key in config.keys():
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in sensitive_patterns):
                sensitive_keys.append(key)
                
        return sensitive_keys
        
    def export_key(self, password: str = None) -> bytes:
        """Export encryption key for backup."""
        if password:
            # Encrypt key with password
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            fernet = Fernet(key)
            encrypted_key = fernet.encrypt(self.encryption_key)
            return salt + encrypted_key
        else:
            return self.encryption_key
            
    def import_key(self, key_data: bytes, password: str = None) -> None:
        """Import encryption key from backup."""
        if password:
            # Decrypt key with password
            salt = key_data[:16]
            encrypted_key = key_data[16:]
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            fernet = Fernet(key)
            self.encryption_key = fernet.decrypt(encrypted_key)
        else:
            self.encryption_key = key_data
            
        self.fernet = Fernet(self.encryption_key)


class SecretResolver:
    """Resolve secret references in configuration."""
    
    def __init__(self, secrets_manager: SecretsManager):
        self.secrets_manager = secrets_manager
        
    async def resolve_secrets(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve secret references in configuration."""
        resolved_config = {}
        
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${secret:"):
                # Extract secret key: ${secret:database.password}
                secret_key = value[9:-1]  # Remove ${secret: and }
                secret_value = await self.secrets_manager.get_secret(secret_key)
                if secret_value is not None:
                    resolved_config[key] = secret_value
                else:
                    logger.warning(f"Secret not found: {secret_key}")
                    resolved_config[key] = value  # Keep original value
            elif isinstance(value, dict):
                resolved_config[key] = await self.resolve_secrets(value)
            elif isinstance(value, list):
                resolved_config[key] = await self._resolve_list_secrets(value)
            else:
                resolved_config[key] = value
                
        return resolved_config
        
    async def _resolve_list_secrets(self, items: List[Any]) -> List[Any]:
        """Resolve secrets in list items."""
        resolved_items = []
        
        for item in items:
            if isinstance(item, str) and item.startswith("${secret:"):
                secret_key = item[9:-1]
                secret_value = await self.secrets_manager.get_secret(secret_key)
                resolved_items.append(secret_value if secret_value is not None else item)
            elif isinstance(item, dict):
                resolved_items.append(await self.resolve_secrets(item))
            elif isinstance(item, list):
                resolved_items.append(await self._resolve_list_secrets(item))
            else:
                resolved_items.append(item)
                
        return resolved_items


class SecureConfigManager:
    """Secure configuration manager with encryption and secrets support."""
    
    def __init__(self, encryption: ConfigEncryption = None, 
                 secrets_manager: SecretsManager = None):
        self.encryption = encryption or ConfigEncryption()
        self.secrets_manager = secrets_manager
        self.secret_resolver = SecretResolver(secrets_manager) if secrets_manager else None
        
    async def load_secure_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Load and decrypt configuration."""
        # First decrypt encrypted values
        decrypted_config = self.encryption.decrypt_config(config)
        
        # Then resolve secret references
        if self.secret_resolver:
            decrypted_config = await self.secret_resolver.resolve_secrets(decrypted_config)
            
        return decrypted_config
        
    def save_secure_config(self, config: Dict[str, Any], 
                          sensitive_keys: List[str] = None) -> Dict[str, Any]:
        """Encrypt sensitive configuration values."""
        return self.encryption.encrypt_config(config, sensitive_keys)
        
    async def store_secret(self, key: str, value: str) -> None:
        """Store a secret value."""
        if self.secrets_manager:
            await self.secrets_manager.set_secret(key, value)
        else:
            raise ValueError("No secrets manager configured")
            
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value."""
        if self.secrets_manager:
            return await self.secrets_manager.get_secret(key)
        return None
        
    def rotate_encryption_key(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Rotate encryption key and re-encrypt configuration."""
        # Decrypt with old key
        decrypted_config = self.encryption.decrypt_config(config)
        
        # Generate new key
        new_encryption = ConfigEncryption()
        
        # Encrypt with new key
        self.encryption = new_encryption
        return self.encryption.encrypt_config(decrypted_config)


# Factory functions
def create_file_secrets_manager(secrets_file: Union[str, Path], 
                               encryption_key: bytes = None) -> FileSecretsManager:
    """Create a file-based secrets manager."""
    return FileSecretsManager(secrets_file, encryption_key)


def create_keyring_secrets_manager(service_name: str = "universal_platform") -> KeyringSecretsManager:
    """Create a keyring-based secrets manager."""
    return KeyringSecretsManager(service_name)


def create_vault_secrets_manager(url: str, token: str = None, 
                                mount_point: str = "secret") -> VaultSecretsManager:
    """Create a Vault-based secrets manager."""
    return VaultSecretsManager(url, token, mount_point)


def create_secure_config_manager(encryption_key: bytes = None, 
                                secrets_manager: SecretsManager = None) -> SecureConfigManager:
    """Create a secure configuration manager."""
    encryption = ConfigEncryption(encryption_key)
    return SecureConfigManager(encryption, secrets_manager)