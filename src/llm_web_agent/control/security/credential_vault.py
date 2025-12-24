"""
Credential Vault - Secure credential storage and management.
"""

from dataclasses import dataclass
from typing import Dict, Optional
from abc import ABC, abstractmethod
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class Credential:
    """
    A stored credential.
    
    Attributes:
        name: Credential name/identifier
        username: Username or email
        password: Password (plaintext in memory only)
        domain: Associated domain
        metadata: Additional credential data
    """
    name: str
    username: str
    password: str
    domain: Optional[str] = None
    metadata: Dict[str, str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ICredentialBackend(ABC):
    """Abstract backend for credential storage."""
    
    @abstractmethod
    def store(self, credential: Credential) -> None:
        """Store a credential."""
        ...
    
    @abstractmethod
    def retrieve(self, name: str) -> Optional[Credential]:
        """Retrieve a credential by name."""
        ...
    
    @abstractmethod
    def delete(self, name: str) -> bool:
        """Delete a credential."""
        ...
    
    @abstractmethod
    def list_names(self) -> list[str]:
        """List all credential names."""
        ...


class EnvironmentCredentialBackend(ICredentialBackend):
    """
    Credential backend using environment variables.
    
    Credentials are stored as:
    - {PREFIX}_{NAME}_USERNAME
    - {PREFIX}_{NAME}_PASSWORD
    """
    
    def __init__(self, prefix: str = "LLM_WEB_AGENT_CRED"):
        self.prefix = prefix
    
    def store(self, credential: Credential) -> None:
        """Store credential in environment (not persistent)."""
        name_upper = credential.name.upper().replace("-", "_")
        os.environ[f"{self.prefix}_{name_upper}_USERNAME"] = credential.username
        os.environ[f"{self.prefix}_{name_upper}_PASSWORD"] = credential.password
    
    def retrieve(self, name: str) -> Optional[Credential]:
        """Retrieve credential from environment."""
        name_upper = name.upper().replace("-", "_")
        username = os.environ.get(f"{self.prefix}_{name_upper}_USERNAME")
        password = os.environ.get(f"{self.prefix}_{name_upper}_PASSWORD")
        
        if username and password:
            return Credential(name=name, username=username, password=password)
        return None
    
    def delete(self, name: str) -> bool:
        """Delete credential from environment."""
        name_upper = name.upper().replace("-", "_")
        deleted = False
        for suffix in ["_USERNAME", "_PASSWORD"]:
            key = f"{self.prefix}_{name_upper}{suffix}"
            if key in os.environ:
                del os.environ[key]
                deleted = True
        return deleted
    
    def list_names(self) -> list[str]:
        """List credential names from environment."""
        names = set()
        for key in os.environ:
            if key.startswith(self.prefix) and key.endswith("_USERNAME"):
                name = key[len(self.prefix)+1:-9]  # Remove prefix and _USERNAME
                names.add(name.lower().replace("_", "-"))
        return list(names)


class CredentialVault:
    """
    Secure credential management.
    
    Provides a unified interface for storing and retrieving credentials
    with pluggable backends (environment, keychain, etc.).
    
    Example:
        >>> vault = CredentialVault()
        >>> vault.store(Credential(name="gmail", username="user@gmail.com", password="xxx"))
        >>> cred = vault.get("gmail")
        >>> print(cred.username)
    """
    
    def __init__(self, backend: Optional[ICredentialBackend] = None):
        """
        Initialize the vault.
        
        Args:
            backend: Storage backend (defaults to environment)
        """
        self._backend = backend or EnvironmentCredentialBackend()
        self._cache: Dict[str, Credential] = {}
    
    def store(self, credential: Credential) -> None:
        """
        Store a credential.
        
        Args:
            credential: Credential to store
        """
        self._backend.store(credential)
        self._cache[credential.name] = credential
        logger.info(f"Stored credential: {credential.name}")
    
    def get(self, name: str) -> Optional[Credential]:
        """
        Get a credential by name.
        
        Args:
            name: Credential name
            
        Returns:
            Credential or None if not found
        """
        # Check cache first
        if name in self._cache:
            return self._cache[name]
        
        # Try backend
        credential = self._backend.retrieve(name)
        if credential:
            self._cache[name] = credential
        return credential
    
    def delete(self, name: str) -> bool:
        """
        Delete a credential.
        
        Args:
            name: Credential name
            
        Returns:
            True if deleted
        """
        self._cache.pop(name, None)
        return self._backend.delete(name)
    
    def list_credentials(self) -> list[str]:
        """List all stored credential names."""
        return self._backend.list_names()
    
    def get_for_domain(self, domain: str) -> Optional[Credential]:
        """
        Get credential for a domain.
        
        Args:
            domain: Domain to match
            
        Returns:
            Matching credential or None
        """
        for name in self.list_credentials():
            cred = self.get(name)
            if cred and cred.domain and domain in cred.domain:
                return cred
        return None
