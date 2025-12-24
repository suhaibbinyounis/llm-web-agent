"""
Sensitive Detector - Detect PII and sensitive data.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import re


class SensitiveType(Enum):
    """Types of sensitive data."""
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    EMAIL = "email"
    PHONE = "phone"
    API_KEY = "api_key"
    PASSWORD = "password"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    CUSTOM = "custom"


@dataclass
class SensitiveMatch:
    """
    A detected sensitive data match.
    
    Attributes:
        sensitive_type: Type of sensitive data
        value: Matched value (may be redacted)
        start: Start position in text
        end: End position in text
        confidence: Detection confidence
    """
    sensitive_type: SensitiveType
    value: str
    start: int
    end: int
    confidence: float = 1.0


class SensitiveDetector:
    """
    Detect sensitive/PII data in text and screenshots.
    
    Example:
        >>> detector = SensitiveDetector()
        >>> matches = detector.detect("My SSN is 123-45-6789")
        >>> print(matches[0].sensitive_type)  # SensitiveType.SSN
        >>> redacted = detector.redact("My SSN is 123-45-6789")
        >>> print(redacted)  # "My SSN is [REDACTED-SSN]"
    """
    
    # Regex patterns for sensitive data
    PATTERNS = {
        SensitiveType.SSN: re.compile(
            r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b'
        ),
        SensitiveType.CREDIT_CARD: re.compile(
            r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
        ),
        SensitiveType.EMAIL: re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ),
        SensitiveType.PHONE: re.compile(
            r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
        ),
        SensitiveType.API_KEY: re.compile(
            r'\b(?:sk-[a-zA-Z0-9]{48}|ghp_[a-zA-Z0-9]{36}|'
            r'[a-zA-Z0-9]{32,})\b'
        ),
    }
    
    # Keywords that might indicate passwords
    PASSWORD_KEYWORDS = [
        "password", "passwd", "pwd", "secret", "token",
    ]
    
    def __init__(self, custom_patterns: Optional[dict] = None):
        """
        Initialize the detector.
        
        Args:
            custom_patterns: Custom regex patterns to add
        """
        self._patterns = self.PATTERNS.copy()
        if custom_patterns:
            for name, pattern in custom_patterns.items():
                self._patterns[SensitiveType.CUSTOM] = re.compile(pattern)
    
    def detect(self, text: str) -> List[SensitiveMatch]:
        """
        Detect sensitive data in text.
        
        Args:
            text: Text to scan
            
        Returns:
            List of sensitive data matches
        """
        matches = []
        
        for sensitive_type, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                matches.append(SensitiveMatch(
                    sensitive_type=sensitive_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                ))
        
        # Sort by position
        matches.sort(key=lambda m: m.start)
        return matches
    
    def has_sensitive_data(self, text: str) -> bool:
        """Check if text contains sensitive data."""
        return len(self.detect(text)) > 0
    
    def redact(
        self,
        text: str,
        replacement_format: str = "[REDACTED-{type}]",
    ) -> str:
        """
        Redact sensitive data from text.
        
        Args:
            text: Text to redact
            replacement_format: Format for replacement (use {type} for type)
            
        Returns:
            Redacted text
        """
        matches = self.detect(text)
        
        # Process in reverse order to maintain positions
        result = text
        for match in reversed(matches):
            replacement = replacement_format.format(type=match.sensitive_type.value.upper())
            result = result[:match.start] + replacement + result[match.end:]
        
        return result
    
    def get_redaction_summary(self, text: str) -> dict:
        """
        Get a summary of redactions that would be made.
        
        Args:
            text: Text to analyze
            
        Returns:
            Summary of sensitive data found
        """
        matches = self.detect(text)
        summary = {}
        
        for match in matches:
            type_name = match.sensitive_type.value
            if type_name not in summary:
                summary[type_name] = 0
            summary[type_name] += 1
        
        return summary
