import os
import uvicorn
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.scheduler import router as scheduler_router
from app.services.config import get_settings, Settings

# Load environment variables
load_dotenv()

# Get settings
settings = get_settings()

# Configure logging based on settings
log_level = logging.DEBUG if settings.debug else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app with config-driven settings
app = FastAPI(
    title=settings.app_name,
    description="Config-driven crypto analysis scheduler dashboard",
    version=settings.app_version,
    debug=settings.debug
)

# Add CORS middleware with config-aware settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [
        "https://*.run.app", 
        "https://*.googleapis.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (create directory if it doesn't exist)
static_dir = "app/static"
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
    logger.info(f"Created static directory: {static_dir}")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API routes
app.include_router(scheduler_router, prefix="/api", tags=["scheduler"])

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, settings: Settings = Depends(get_settings)):
    """Main dashboard page with config-driven template variables"""
    logger.info(f"Serving dashboard for {settings.app_name} v{settings.app_version}")
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "project_id": settings.google_cloud_project,
        "region": settings.google_cloud_region,
        "function_url": settings.crypto_function_url,
        "wallet_api_url": settings.wallet_api_url,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "debug": settings.debug
    })

@app.get("/health")
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint with config information"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "debug": settings.debug,
        "environment": "development" if settings.debug else "production",
        "google_cloud_project": settings.google_cloud_project,
        "google_cloud_region": settings.google_cloud_region
    }

@app.get("/config")
async def get_app_config(settings: Settings = Depends(get_settings)):
    """Get application configuration (safe values only)"""
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "debug": settings.debug,
        "google_cloud_project": settings.google_cloud_project,
        "google_cloud_region": settings.google_cloud_region,
        "crypto_function_url": settings.crypto_function_url,
        "wallet_api_url": settings.wallet_api_url,
        "api_timeout": settings.api_timeout,
        "wallet_api_timeout": settings.wallet_api_timeout,
        "max_retries": settings.max_retries,
        "rate_limit_enabled": settings.rate_limit_enabled,
        # Note: Don't expose secret_key, admin_password, etc.
    }

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    settings = get_settings()
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"📊 Debug mode: {settings.debug}")
    logger.info(f"☁️ Google Cloud Project: {settings.google_cloud_project}")
    logger.info(f"🌍 Region: {settings.google_cloud_region}")
    logger.info(f"🔗 Crypto Function: {settings.crypto_function_url}")
    logger.info(f"💰 Wallet API: {settings.wallet_api_url}")
    
    # Test connectivity to wallet API on startup
    try:
        import httpx
        async with httpx.AsyncClient(timeout=settings.wallet_api_timeout) as client:
            response = await client.get(f"{settings.wallet_api_url}/wallets/count")
            if response.status_code == 200:
                data = response.json()
                wallet_count = data.get("count", 0)
                logger.info(f"✅ Wallet API connected: {wallet_count} wallets available")
            else:
                logger.warning(f"⚠️ Wallet API returned status {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to wallet API: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    settings = get_settings()
    logger.info(f"🛑 Shutting down {settings.app_name}")

if __name__ == "__main__":
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 8080))
    
    # Use config settings for uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=settings.debug,  # Auto-reload in debug mode
        log_level="debug" if settings.debug else "info"
    )