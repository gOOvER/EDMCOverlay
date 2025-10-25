"""
Configuration management for EDMCOverlay
"""

import json
import logging
import os
from typing import Any, Dict, Optional

# Default configuration
DEFAULT_CONFIG = {
    "server": {
        "address": "127.0.0.1",
        "port": 5010,
        "timeout": 5.0,
        "reconnect_attempts": 3,
        "reconnect_delay": 1.0,
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    },
    "security": {
        "max_message_length": 1000,
        "allowed_commands": ["exit", "clear", "status"],
    },
    "overlay": {"default_ttl": 4, "default_color": "white", "default_size": "normal"},
}


class Config:
    """Configuration manager for EDMCOverlay"""

    def __init__(self, config_file: Optional[str] = None):
        self._config = DEFAULT_CONFIG.copy()
        self._config_file = config_file or os.path.join(
            os.path.dirname(__file__), "edmcoverlay_config.json"
        )
        self.load()

    def load(self) -> None:
        """Load configuration from file"""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    self._merge_config(self._config, user_config)
                logging.info(f"Configuration loaded from {self._config_file}")
            except Exception as e:
                logging.warning(f"Failed to load config from {self._config_file}: {e}")

    def save(self) -> None:
        """Save current configuration to file"""
        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
            logging.info(f"Configuration saved to {self._config_file}")
        except Exception as e:
            logging.error(f"Failed to save config to {self._config_file}: {e}")

    def _merge_config(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Recursively merge configuration dictionaries"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get("server.port")
        """
        keys = path.split(".")
        value = self._config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, path: str, value: Any) -> None:
        """
        Set configuration value using dot notation
        Example: config.set("server.port", 5011)
        """
        keys = path.split(".")
        config = self._config

        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set the value
        config[keys[-1]] = value

    @property
    def server_address(self) -> str:
        return self.get("server.address")

    @property
    def server_port(self) -> int:
        return self.get("server.port")

    @property
    def server_timeout(self) -> float:
        return self.get("server.timeout")

    @property
    def reconnect_attempts(self) -> int:
        return self.get("server.reconnect_attempts")

    @property
    def reconnect_delay(self) -> float:
        return self.get("server.reconnect_delay")

    @property
    def max_message_length(self) -> int:
        return self.get("security.max_message_length")

    @property
    def allowed_commands(self) -> list:
        return self.get("security.allowed_commands")

    @property
    def default_ttl(self) -> int:
        return self.get("overlay.default_ttl")

    @property
    def default_color(self) -> str:
        return self.get("overlay.default_color")

    @property
    def default_size(self) -> str:
        return self.get("overlay.default_size")


# Global configuration instance
config = Config()
