from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional
import os

class Settings(BaseSettings):
    """Settings that read from .env file and environment variables"""
    
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
        # This tells Pydantic where to find the .env file
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # WALLET_API_URL or wallet_api_url both work
        extra = "ignore"  # Ignore extra environment variables
        
    def __init__(self, **kwargs):
        """Initialize settings with debug info"""
        super().__init__(**kwargs)
        
        # Debug: Show where values are coming from
        if os.getenv("DEBUG", "").lower() in ["true", "1", "yes"]:
            print(f"🔧 Config Debug:")
            print(f"   .env file exists: {os.path.exists('.env')}")
            print(f"   WALLET_API_URL from env: {os.getenv('WALLET_API_URL', 'NOT_SET')}")
            print(f"   DEBUG from env: {os.getenv('DEBUG', 'NOT_SET')}")
            print(f"   Loaded wallet_api_url: {self.wallet_api_url}")
            print(f"   Loaded debug: {self.debug}")

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Test function to verify config is working
def test_config():
    """Test function to verify environment loading"""
    print("🧪 Testing configuration...")
    
    settings = get_settings()
    
    print(f"App Name: {settings.app_name}")
    print(f"Debug Mode: {settings.debug}")
    print(f"Wallet API URL: {settings.wallet_api_url}")
    print(f"Google Cloud Project: {settings.google_cloud_project}")
    
    # Check if we're getting values from .env
    env_debug = os.getenv("DEBUG")
    if env_debug:
        print(f"✅ Reading DEBUG from environment: {env_debug}")
    else:
        print("⚠️ DEBUG not found in environment variables")
        
    env_wallet_url = os.getenv("WALLET_API_URL")
    if env_wallet_url:
        print(f"✅ Reading WALLET_API_URL from environment: {env_wallet_url}")
    else:
        print("⚠️ WALLET_API_URL not found in environment variables")
    
    return settings

if __name__ == "__main__":
    # Test the configuration when run directly
    test_config()