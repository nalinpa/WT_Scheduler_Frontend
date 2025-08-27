import os
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.api.scheduler import router as scheduler_router
from app.services.config import get_settings

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Crypto Scheduler Dashboard",
    description="Web dashboard for managing crypto analysis scheduler jobs",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API routes
app.include_router(scheduler_router, prefix="/api", tags=["scheduler"])

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    settings = get_settings()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "project_id": settings.google_cloud_project,
        "region": settings.google_cloud_region,
        "function_url": settings.crypto_function_url,
        "app_name": settings.app_name
    })

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "crypto-scheduler-dashboard",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
