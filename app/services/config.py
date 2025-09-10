from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # Google Cloud Configuration
    google_cloud_project: str = Field(
        default="crypto-tracker-cloudrun",
        description="Google Cloud Project ID"
    )
    google_cloud_region: str = Field(
        default="asia-southeast1", 
        description="Google Cloud Region"
    )
    
    # Service URLs
    crypto_function_url: str = Field(
        default="https://crypto-analysis-function-qz6f5mkbmq-as.a.run.app",
        description="Crypto analysis function URL"
    )
    wallet_api_url: str = Field(
        default="https://wallet-api-bigquery-qz6f5mkbmq-as.a.run.app",
        description="Wallet API URL"
    )
    
    # Application Settings
    app_name: str = Field(
        default="Crypto Scheduler Dashboard",
        description="Application name"
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application version"
    )
    debug: bool = Field(
        default=True,
        description="Enable debug mode"
    )
    
    # Security Settings
    secret_key: str = Field(
        default="your-secret-key-here",
        description="Secret key for security operations"
    )
    admin_password: str = Field(
        default="admin123",
        description="Admin password"
    )
    
    # API Settings
    api_timeout: int = Field(
        default=30,
        description="Default API timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum API retries"
    )
    
    # Wallet API specific settings
    wallet_api_timeout: int = Field(
        default=30,
        description="Wallet API timeout in seconds"
    )
    
    # Rate limiting (optional)
    rate_limit_enabled: bool = Field(
        default=False,
        description="Enable rate limiting"
    )
    rate_limit_requests_per_minute: int = Field(
        default=60,
        description="Requests per minute per IP"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # Allow both upper and lower case env vars
        extra = "ignore"  # Ignore extra environment variables

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()