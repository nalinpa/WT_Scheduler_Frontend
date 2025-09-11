# Enhanced Logging with structlog
# Add to requirements.txt: structlog==23.2.0

import structlog
import logging
import json
import sys
from typing import Any, Dict
from app.services.config import get_settings

def setup_logging():
    """Setup structured logging with JSON output for production"""
    settings = get_settings()
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Use JSON in production, pretty print in development
            structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.debug else logging.INFO,
    )
    
    # Setup Google Cloud Logging if available
    if not settings.debug:
        try:
            from google.cloud import logging as cloud_logging
            client = cloud_logging.Client()
            client.setup_logging()
        except ImportError:
            pass  # Google Cloud Logging not available

# Enhanced logger with crypto-specific context
class CryptoLogger:
    """Enhanced logger for crypto scheduler with automatic context"""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        self.settings = get_settings()
    
    def wallet_api_call(self, action: str, **kwargs):
        """Log wallet API calls with structured data"""
        return self.logger.bind(
            component="wallet_api",
            action=action,
            api_url=self.settings.wallet_api_url,
            **kwargs
        )
    
    def job_operation(self, job_id: str, operation: str, **kwargs):
        """Log job operations with structured data"""
        return self.logger.bind(
            component="job_scheduler",
            job_id=job_id,
            operation=operation,
            **kwargs
        )
    
    def cache_operation(self, operation: str, key: str = None, **kwargs):
        """Log cache operations with structured data"""
        return self.logger.bind(
            component="cache",
            operation=operation,
            cache_key=key,
            **kwargs
        )
    
    def api_request(self, method: str, endpoint: str, **kwargs):
        """Log API requests with structured data"""
        return self.logger.bind(
            component="api",
            http_method=method,
            endpoint=endpoint,
            **kwargs
        )
    
    def performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        return self.logger.bind(
            component="performance",
            operation=operation,
            duration_ms=round(duration * 1000, 2),
            **kwargs
        )

# Global logger instances
setup_logging()
crypto_logger = CryptoLogger("crypto_scheduler")