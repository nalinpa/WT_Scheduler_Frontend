
Write-Host "Creating Crypto Scheduler Dashboard Project (FastAPI)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# Create directory structure
$directories = @(
    "app",
    "app/api",
    "app/models",
    "app/services", 
    "app/static/css",
    "app/static/js",
    "app/templates",
    "config",
    "scripts",
    "docs"
)

foreach ($dir in $directories) {
    New-Item -ItemType Directory -Path $dir -Force
    Write-Host "Created directory: $dir" -ForegroundColor Green
}

Write-Host "`nCreating project files..." -ForegroundColor Yellow

# requirements.txt
$requirements = @'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
google-cloud-scheduler==2.13.3
google-auth==2.23.4
python-dotenv==1.0.0
jinja2==3.1.2
aiofiles==23.2.0
python-multipart==0.0.6
httpx==0.25.2
'@
$requirements | Out-File -Encoding UTF8 -FilePath "requirements.txt"

# .env.template
$envTemplate = @'
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=crypto-tracker-cloudrun
GOOGLE_CLOUD_REGION=asia-southeast1

# Crypto Analysis Function URL
CRYPTO_FUNCTION_URL=https://crypto-analysis-function-qz6f5mkbmq-as.a.run.app

# Application Settings
APP_NAME=Crypto Scheduler Dashboard
APP_VERSION=1.0.0
DEBUG=true

# Authentication (optional)
SECRET_KEY=your-secret-key-here
ADMIN_PASSWORD=admin123
'@
$envTemplate | Out-File -Encoding UTF8 -FilePath ".env.template"

# main.py (FastAPI application)
$mainPy = @'
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
'@
$mainPy | Out-File -Encoding UTF8 -FilePath "main.py"

# app/__init__.py
$appInit = @'
"""Crypto Scheduler Dashboard Application"""
__version__ = "1.0.0"
'@
$appInit | Out-File -Encoding UTF8 -FilePath "app/__init__.py"

# app/models/job.py
$jobModel = @'
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class JobState(str, Enum):
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"

class NetworkType(str, Enum):
    ETHEREUM = "ethereum"
    BASE = "base"

class AnalysisType(str, Enum):
    BUY = "buy"
    SELL = "sell"

class SchedulerJob(BaseModel):
    id: str
    name: str
    network: NetworkType
    analysis_type: AnalysisType
    schedule: str  # Cron expression
    state: JobState = JobState.ENABLED
    description: Optional[str] = None
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None
    execution_count: int = 0
    success_count: int = 0
    function_url: str

class JobCreateRequest(BaseModel):
    id: str
    name: str
    network: NetworkType
    analysis_type: AnalysisType
    schedule: str
    description: Optional[str] = None
    num_wallets: int = 100
    days_back: float = 1.0

class JobUpdateRequest(BaseModel):
    schedule: Optional[str] = None
    description: Optional[str] = None
    num_wallets: Optional[int] = None
    days_back: Optional[float] = None

class JobExecutionRequest(BaseModel):
    num_wallets: int = 100
    days_back: float = 1.0
'@
$jobModel | Out-File -Encoding UTF8 -FilePath "app/models/job.py"

# app/services/config.py
$configService = @'
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
'@
$configService | Out-File -Encoding UTF8 -FilePath "app/services/config.py"

# app/services/scheduler.py
$schedulerService = @'
from google.cloud import scheduler_v1
from google.auth.exceptions import DefaultCredentialsError
from app.models.job import SchedulerJob, JobState, JobCreateRequest
from app.services.config import get_settings
from typing import List, Optional
import json
import logging

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        self.settings = get_settings()
        self.project_id = self.settings.google_cloud_project
        self.region = self.settings.google_cloud_region
        self.parent = f"projects/{self.project_id}/locations/{self.region}"
        
        try:
            self.client = scheduler_v1.CloudSchedulerClient()
            logger.info(f"Connected to Cloud Scheduler: {self.parent}")
        except DefaultCredentialsError:
            logger.warning("Google Cloud credentials not found. Running in mock mode.")
            self.client = None

    async def list_jobs(self) -> List[SchedulerJob]:
        """List all scheduler jobs"""
        if not self.client:
            return self._get_mock_jobs()
        
        try:
            jobs = []
            for job in self.client.list_jobs(request={"parent": self.parent}):
                job_id = job.name.split('/')[-1]
                
                # Parse job payload to get network and analysis type
                payload = json.loads(job.http_target.body.decode('utf-8'))
                
                scheduler_job = SchedulerJob(
                    id=job_id,
                    name=job_id.replace('-', ' ').title(),
                    network=payload.get('network', 'ethereum'),
                    analysis_type=payload.get('analysis_type', 'buy'),
                    schedule=job.schedule,
                    state=JobState(job.state.name),
                    description=job.description or f"Analysis job for {payload.get('network', 'ethereum')}",
                    function_url=job.http_target.uri
                )
                jobs.append(scheduler_job)
                
            return jobs
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            return []

    async def get_job(self, job_id: str) -> Optional[SchedulerJob]:
        """Get a specific job"""
        jobs = await self.list_jobs()
        return next((job for job in jobs if job.id == job_id), None)

    async def create_job(self, job_request: JobCreateRequest) -> bool:
        """Create a new scheduler job"""
        if not self.client:
            logger.info(f"Mock: Creating job {job_request.id}")
            return True

        try:
            job_path = f"{self.parent}/jobs/{job_request.id}"
            
            # Create job payload
            payload = {
                "network": job_request.network,
                "analysis_type": job_request.analysis_type,
                "num_wallets": job_request.num_wallets,
                "days_back": job_request.days_back
            }
            
            job = {
                "name": job_path,
                "description": job_request.description or f"{job_request.network} {job_request.analysis_type} analysis",
                "schedule": job_request.schedule,
                "time_zone": "UTC",
                "http_target": {
                    "uri": self.settings.crypto_function_url,
                    "http_method": scheduler_v1.HttpMethod.POST,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(payload).encode('utf-8')
                }
            }
            
            self.client.create_job(request={"parent": self.parent, "job": job})
            logger.info(f"Created job: {job_request.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating job {job_request.id}: {e}")
            return False

    async def pause_job(self, job_id: str) -> bool:
        """Pause a job"""
        if not self.client:
            logger.info(f"Mock: Pausing job {job_id}")
            return True

        try:
            job_path = f"{self.parent}/jobs/{job_id}"
            self.client.pause_job(request={"name": job_path})
            logger.info(f"Paused job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error pausing job {job_id}: {e}")
            return False

    async def resume_job(self, job_id: str) -> bool:
        """Resume a job"""
        if not self.client:
            logger.info(f"Mock: Resuming job {job_id}")
            return True

        try:
            job_path = f"{self.parent}/jobs/{job_id}"
            self.client.resume_job(request={"name": job_path})
            logger.info(f"Resumed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error resuming job {job_id}: {e}")
            return False

    async def run_job_now(self, job_id: str) -> bool:
        """Run a job immediately"""
        if not self.client:
            logger.info(f"Mock: Running job {job_id} now")
            return True

        try:
            job_path = f"{self.parent}/jobs/{job_id}"
            self.client.run_job(request={"name": job_path})
            logger.info(f"Triggered job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error running job {job_id}: {e}")
            return False

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job"""
        if not self.client:
            logger.info(f"Mock: Deleting job {job_id}")
            return True

        try:
            job_path = f"{self.parent}/jobs/{job_id}"
            self.client.delete_job(request={"name": job_path})
            logger.info(f"Deleted job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {e}")
            return False

    def _get_mock_jobs(self) -> List[SchedulerJob]:
        """Return mock jobs for development"""
        return [
            SchedulerJob(
                id="crypto-buy-analysis-ethereum",
                name="Ethereum Buy Analysis",
                network="ethereum",
                analysis_type="buy",
                schedule="0 */4 * * *",
                state=JobState.ENABLED,
                description="Analyzes buy transactions on Ethereum",
                function_url=self.settings.crypto_function_url
            ),
            SchedulerJob(
                id="crypto-sell-analysis-ethereum", 
                name="Ethereum Sell Analysis",
                network="ethereum",
                analysis_type="sell",
                schedule="30 */6 * * *",
                state=JobState.PAUSED,
                description="Analyzes sell transactions on Ethereum",
                function_url=self.settings.crypto_function_url
            )
        ]

# Global instance
scheduler_service = SchedulerService()
'@
$schedulerService | Out-File -Encoding UTF8 -FilePath "app/services/scheduler.py"

Write-Host "✅ Project structure created successfully!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. cd $ProjectPath" -ForegroundColor White
Write-Host "2. Copy .env.template to .env and configure your settings" -ForegroundColor White  
Write-Host "3. pip install -r requirements.txt" -ForegroundColor White
Write-Host "4. python main.py" -ForegroundColor White
Write-Host "`nProject created at: $(Get-Location)\$ProjectPath" -ForegroundColor Cyan