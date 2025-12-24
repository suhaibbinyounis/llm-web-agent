"""
Security submodule - Credential management and sensitive data handling.
"""

from llm_web_agent.control.security.credential_vault import CredentialVault, Credential
from llm_web_agent.control.security.sensitive_detector import SensitiveDetector, SensitiveMatch

__all__ = [
    "CredentialVault",
    "Credential",
    "SensitiveDetector",
    "SensitiveMatch",
]
