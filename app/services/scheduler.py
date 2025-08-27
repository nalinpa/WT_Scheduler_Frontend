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
