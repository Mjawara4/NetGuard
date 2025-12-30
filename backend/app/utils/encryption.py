"""
Encryption utilities for sensitive database fields.
Uses Fernet symmetric encryption for encrypting/decrypting sensitive data.
"""
from cryptography.fernet import Fernet
from app.core.config import settings
import base64
import logging

logger = logging.getLogger(__name__)

# Cache the Fernet instance
_fernet_instance = None

def get_fernet():
    """Get or create Fernet instance for encryption/decryption."""
    global _fernet_instance
    if _fernet_instance is None:
        encryption_key = settings.ENCRYPTION_KEY
        if not encryption_key:
            logger.warning("ENCRYPTION_KEY not set. Encryption disabled. Set ENCRYPTION_KEY in .env to enable encryption.")
            return None
        
        try:
            # Ensure key is bytes
            if isinstance(encryption_key, str):
                encryption_key = encryption_key.encode()
            _fernet_instance = Fernet(encryption_key)
        except Exception as e:
            logger.error(f"Failed to initialize Fernet encryption: {e}")
            return None
    return _fernet_instance

def encrypt_value(value: str) -> str:
    """
    Encrypt a string value.
    Returns the encrypted value as a base64-encoded string.
    If encryption is not available, returns the original value (backward compatibility).
    """
    if not value:
        return value
    
    fernet = get_fernet()
    if fernet is None:
        # Encryption not available - return as-is for backward compatibility
        return value
    
    try:
        encrypted = fernet.encrypt(value.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        # Return original value on error (backward compatibility)
        return value

def decrypt_value(value: str) -> str:
    """
    Decrypt a string value.
    Supports both encrypted and plaintext values (dual-read mode for migration).
    If decryption fails, assumes it's plaintext (backward compatibility).
    """
    if not value:
        return value
    
    fernet = get_fernet()
    if fernet is None:
        # Encryption not available - assume plaintext
        return value
    
    try:
        # Try to decrypt
        decrypted = fernet.decrypt(value.encode())
        return decrypted.decode()
    except Exception as e:
        # If decryption fails, assume it's plaintext (for backward compatibility during migration)
        logger.debug(f"Decryption failed (assuming plaintext): {e}")
        return value

def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be encrypted.
    This is a heuristic - encrypted values are base64-encoded bytes from Fernet.
    """
    if not value:
        return False
    
    try:
        # Try to decode as base64
        decoded = base64.urlsafe_b64decode(value)
        # Fernet encrypted values have a specific structure
        return len(decoded) > 0 and len(value) > 32  # Encrypted values are typically longer
    except Exception:
        return False
