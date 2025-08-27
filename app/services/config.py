from pydantic import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    google_cloud_project: str = "crypto-tracker-cloudrun"
    google_cloud_region: str = "asia-southeast1"
    crypto_function_url: str = "https://crypto-analysis-function-qz6f5mkbmq-as.a.run.app"
    app_name: str = "Crypto Scheduler Dashboard"
    app_version: str = "1.0.0"
    debug: bool = True
    secret_key: str = "your-secret-key-here"
    admin_password: str = "admin123"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
