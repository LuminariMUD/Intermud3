"""Configuration loader for I3 Gateway."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import ValidationError

from .models import Settings


def expand_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively expand environment variables in configuration."""
    if isinstance(config, dict):
        result = {}
        for key, value in config.items():
            result[key] = expand_env_vars(value)
        return result
    elif isinstance(config, list):
        return [expand_env_vars(item) for item in config]
    elif isinstance(config, str):
        # Check for environment variable pattern ${VAR:default}
        if config.startswith("${") and "}" in config:
            var_expr = config[2:config.index("}")]
            if ":" in var_expr:
                var_name, default_value = var_expr.split(":", 1)
                return os.environ.get(var_name, default_value)
            else:
                return os.environ.get(var_expr, config)
    return config


def load_config(config_path: Path) -> Settings:
    """Load configuration from YAML file with environment variable expansion."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, "r") as f:
        raw_config = yaml.safe_load(f)
    
    # Expand environment variables
    config = expand_env_vars(raw_config)
    
    # Create and validate settings
    try:
        return Settings(**config)
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}")