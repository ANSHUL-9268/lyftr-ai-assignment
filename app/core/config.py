"""
Application configuration using 12-factor environment variables.
"""
import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = Field(default="WhatsApp Webhook Service")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    # Security
    webhook_secret: Optional[str] = Field(default=None, description="HMAC-SHA256 secret for webhook validation")
    
    # Database
    database_url: str = Field(default="sqlite:///./data/messages.db")
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")  # json or text
    
    @property
    def is_webhook_secret_configured(self) -> bool:
        """Check if webhook secret is properly configured."""
        return bool(self.webhook_secret and len(self.webhook_secret) > 0)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
