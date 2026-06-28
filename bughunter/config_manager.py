import yaml
import os
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Optional

CONFIG_DIR = Path(".bughunter")
CONFIG_FILE = CONFIG_DIR / "config.yml"

class Profile(BaseModel):
    provider: str
    model: str
    api_key: str

class AppConfig(BaseModel):
    profiles: Dict[str, Profile] = {}
    active_profile: Optional[str] = None

class ConfigManager:
    @staticmethod
    def load() -> AppConfig:
        if not CONFIG_FILE.exists():
            return AppConfig()
        try:
            with open(CONFIG_FILE, "r") as f:
                data = yaml.safe_load(f)
                if not data:
                    return AppConfig()
                return AppConfig(**data)
        except Exception:
            return AppConfig()

    @staticmethod
    def save(config: AppConfig):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            yaml.safe_dump(config.model_dump(), f)

    @staticmethod
    def add_profile(name: str, provider: str, model: str, api_key: str):
        config = ConfigManager.load()
        config.profiles[name] = Profile(provider=provider, model=model, api_key=api_key)
        if not config.active_profile:
            config.active_profile = name
        ConfigManager.save(config)

    @staticmethod
    def set_active(name: str) -> bool:
        config = ConfigManager.load()
        if name in config.profiles:
            config.active_profile = name
            ConfigManager.save(config)
            return True
        return False

    @staticmethod
    def get_active_profile() -> Optional[Profile]:
        config = ConfigManager.load()
        if config.active_profile and config.active_profile in config.profiles:
            return config.profiles[config.active_profile]
        return None

    @staticmethod
    def get_profiles() -> Dict[str, Profile]:
        return ConfigManager.load().profiles

    @staticmethod
    def delete_profile(name: str) -> bool:
        config = ConfigManager.load()
        if name in config.profiles:
            del config.profiles[name]
            # Reset active if we deleted it
            if config.active_profile == name:
                config.active_profile = next(iter(config.profiles.keys())) if config.profiles else None
            ConfigManager.save(config)
            return True
        return False
