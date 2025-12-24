"""
Config Loader - Load and merge configuration from multiple sources.

This module provides utilities for loading configuration from YAML files,
environment variables, and CLI arguments, with proper precedence.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from dotenv import load_dotenv

from llm_web_agent.config.settings import Settings


class ConfigLoader:
    """
    Configuration loader that merges settings from multiple sources.
    
    Priority order (highest to lowest):
    1. Explicit overrides passed to load()
    2. Environment variables
    3. Config file
    4. Default values
    """
    
    DEFAULT_CONFIG_PATHS = [
        Path("config.yaml"),
        Path("config.yml"),
        Path("config/default.yaml"),
        Path.home() / ".config" / "llm-web-agent" / "config.yaml",
    ]
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize the config loader.
        
        Args:
            config_path: Optional explicit path to config file
        """
        self.config_path = Path(config_path) if config_path else None
        self._file_config: Dict[str, Any] = {}
    
    def find_config_file(self) -> Optional[Path]:
        """
        Find the configuration file to load.
        
        Returns:
            Path to config file, or None if not found
        """
        if self.config_path and self.config_path.exists():
            return self.config_path
        
        for path in self.DEFAULT_CONFIG_PATHS:
            if path.exists():
                return path
        
        return None
    
    def load_yaml_config(self, path: Path) -> Dict[str, Any]:
        """
        Load configuration from a YAML file.
        
        Args:
            path: Path to the YAML file
            
        Returns:
            Configuration dictionary
        """
        with open(path, "r") as f:
            config = yaml.safe_load(f)
            return config if config else {}
    
    def load(
        self,
        env_file: Optional[Union[str, Path]] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Settings:
        """
        Load settings from all sources.
        
        Args:
            env_file: Optional path to .env file
            overrides: Optional dictionary of values to override
            
        Returns:
            Complete Settings instance
        """
        # Load .env file
        if env_file:
            load_dotenv(env_file)
        else:
            # Try to load from default locations
            for env_path in [Path(".env"), Path(".env.local")]:
                if env_path.exists():
                    load_dotenv(env_path)
                    break
        
        # Load config file
        config_file = self.find_config_file()
        if config_file:
            self._file_config = self.load_yaml_config(config_file)
        
        # Create settings (Pydantic will automatically load from env vars)
        settings = Settings(**self._file_config)
        
        # Apply overrides
        if overrides:
            settings = settings.merge_with(overrides)
        
        return settings


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    env_file: Optional[Union[str, Path]] = None,
    **overrides: Any,
) -> Settings:
    """
    Convenience function to load configuration.
    
    Args:
        config_path: Optional path to config file
        env_file: Optional path to .env file
        **overrides: Keyword arguments to override settings
        
    Returns:
        Complete Settings instance
        
    Example:
        >>> settings = load_config()
        >>> settings = load_config(config_path="my-config.yaml")
        >>> settings = load_config(browser={"headless": False})
    """
    loader = ConfigLoader(config_path)
    return loader.load(env_file=env_file, overrides=overrides if overrides else None)
