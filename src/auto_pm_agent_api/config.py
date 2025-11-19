"""Configuration management for the application."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "Awesome Agent API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # LLM Configuration
    model_name: str = "gpt-3.5-turbo"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Plane API Configuration
    plane_api_key: Optional[str] = None
    plane_workspace_slug: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "app.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
