from fastapi import APIRouter, HTTPException, Depends
from app.models.job import (
    SchedulerJob, JobCreateRequest, JobUpdateRequest, 
    JobExecutionRequest, NetworkType, AnalysisType
)
from app.services.scheduler import scheduler_service
from app.services.config import get_settings, Settings
from typing import List
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Wallet API endpoint
WALLET_API_URL = "https://wallet-api-bigquery-qz6f5mkbmq-as.a.run.app"

@router.get("/wallets/count")
async def get_wallet_count(settings: Settings = Depends(get_settings)):
    """Get the current wallet count from the wallet API"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{settings.wallet_api_url}/wallets/count")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if isinstance(data, dict) and 'count' in data:
                        count = data.get("count", 0)
                    elif isinstance(data, dict) and len(data) == 1:
                        count = list(data.values())[0]
                    elif isinstance(data, (int, float)):
                        count = int(data)
                    elif isinstance(data, str) and data.isdigit():
                        count = int(data)
                    else:
                        logger.warning(f"Unexpected wallet API response format: {data}")
                        count = 1000
                        
                except Exception as parse_error:
                    logger.warning(f"JSON parsing failed: {parse_error}")
                    try:
                        text_response = response.text.strip()
                        count = int(text_response)
                    except ValueError:
                        logger.error(f"Could not parse wallet count from: {text_response}")
                        count = 1000
                
                logger.info(f"Successfully retrieved wallet count: {count}")
                return {
                    "success": True,
                    "count": count,
                    "source": "wallet-api"
                }
            else:
                logger.error(f"Wallet API returned HTTP {response.status_code}")
                return {
                    "success": False,
                    "count": 1000,
                    "source": "fallback",
                    "error": f"API returned HTTP {response.status_code}"
                }
                
    except Exception as e:
        logger.error(f"Error fetching wallet count: {e}")
        return {
            "success": False,
            "count": 1000,
            "source": "fallback",
            "error": str(e)
        }

@router.get("/jobs", response_model=List[SchedulerJob])
async def list_jobs():
    """Get all scheduler jobs"""
    try:
        logger.info("Fetching jobs from scheduler service")
        jobs = await scheduler_service.list_jobs()
        logger.info(f"Successfully retrieved {len(jobs)} jobs")
        return jobs
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}", response_model=SchedulerJob)
async def get_job(job_id: str):
    """Get a specific job"""
    try:
        job = await scheduler_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs", response_model=dict)
async def create_job(job_request: JobCreateRequest, settings: Settings = Depends(get_settings)):
    """Create a new scheduler job - ALWAYS uses max available wallets"""
    try:
        # Always get the current max wallet count
        wallet_count_data = await get_wallet_count(settings)
        actual_wallet_count = wallet_count_data["count"]
        
        # Override with max wallets
        job_request.num_wallets = actual_wallet_count
        
        logger.info(f"Creating job {job_request.id} with {actual_wallet_count} wallets")
        
        success = await scheduler_service.create_job(job_request)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create job")
        
        return {
            "success": True, 
            "message": f"Job {job_request.id} created successfully with {actual_wallet_count} wallets",
            "wallet_count": actual_wallet_count,
            "wallet_source": wallet_count_data["source"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/jobs/{job_id}/schedule")
async def update_job_schedule(job_id: str, schedule_update: dict):
    """Update a job's schedule"""
    try:
        new_schedule = schedule_update.get("schedule")
        if not new_schedule:
            raise HTTPException(status_code=400, detail="Schedule is required")
        
        # Validate cron expression format (basic validation)
        cron_parts = new_schedule.strip().split()
        if len(cron_parts) != 5:
            raise HTTPException(status_code=400, detail="Cron expression must have exactly 5 parts")
        
        # Get the current job
        job = await scheduler_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Update the job with new schedule
        success = await scheduler_service.update_job_schedule(job_id, new_schedule)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update job schedule")
        
        return {
            "success": True, 
            "message": f"Job {job_id} schedule updated to: {new_schedule}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job schedule {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str, execution_request: JobExecutionRequest = None, settings: Settings = Depends(get_settings)):
    """Run a job immediately with max wallets"""
    try:
        # Always use max wallets
        wallet_count_data = await get_wallet_count(settings)
        actual_wallet_count = wallet_count_data["count"]
        
        if execution_request is None:
            execution_request = JobExecutionRequest()
        
        execution_request.num_wallets = actual_wallet_count
        
        logger.info(f"Running job {job_id} immediately with {actual_wallet_count} wallets")
        
        # Trigger via scheduler
        scheduler_success = await scheduler_service.run_job_now(job_id)
        
        # Also call function directly
        job = await scheduler_service.get_job(job_id)
        if job:
            payload = {
                "network": job.network,
                "analysis_type": job.analysis_type,
                "num_wallets": actual_wallet_count,
                "days_back": execution_request.days_back
            }
            
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(settings.crypto_function_url, json=payload)
                    
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "message": f"Job {job_id} executed successfully with {actual_wallet_count} wallets",
                        "result": {
                            "transactions": result.get("total_transactions", 0),
                            "tokens": result.get("unique_tokens", 0),
                            "eth_value": result.get("total_eth_value", 0),
                            "wallets_used": actual_wallet_count
                        }
                    }
                else:
                    return {
                        "success": scheduler_success,
                        "message": f"Job {job_id} triggered via scheduler (function call failed: HTTP {response.status_code})",
                        "wallets_used": actual_wallet_count
                    }
                    
            except Exception as func_error:
                logger.warning(f"Direct function call failed: {func_error}")
                return {
                    "success": scheduler_success,
                    "message": f"Job {job_id} triggered via scheduler (direct call failed)",
                    "wallets_used": actual_wallet_count
                }
        
        return {
            "success": scheduler_success, 
            "message": f"Job {job_id} triggered with {actual_wallet_count} wallets",
            "wallets_used": actual_wallet_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """Pause a job"""
    try:
        success = await scheduler_service.pause_job(job_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to pause job")
        
        return {"success": True, "message": f"Job {job_id} paused"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """Resume a job"""
    try:
        success = await scheduler_service.resume_job(job_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to resume job")
        
        return {"success": True, "message": f"Job {job_id} resumed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job"""
    try:
        success = await scheduler_service.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to delete job")
        
        return {"success": True, "message": f"Job {job_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/pause-all")
async def pause_all_jobs():
    """Pause all jobs"""
    try:
        jobs = await scheduler_service.list_jobs()
        results = []
        
        for job in jobs:
            if job.state.value == "ENABLED":
                success = await scheduler_service.pause_job(job.id)
                results.append({"job_id": job.id, "success": success})
        
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "success": True,
            "message": f"Paused {success_count}/{len(results)} jobs",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error pausing all jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/resume-all")
async def resume_all_jobs():
    """Resume all jobs"""
    try:
        jobs = await scheduler_service.list_jobs()
        results = []
        
        for job in jobs:
            if job.state.value == "PAUSED":
                success = await scheduler_service.resume_job(job.id)
                results.append({"job_id": job.id, "success": success})
        
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "success": True,
            "message": f"Resumed {success_count}/{len(results)} jobs",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error resuming all jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/update-wallet-counts")
async def update_all_jobs_wallet_counts(settings: Settings = Depends(get_settings)):
    """Update all existing jobs to use the current maximum wallet count"""
    try:
        logger.info('Updating all jobs to use maximum wallet count...')
        
        # Get current max wallet count
        wallet_count_data = await get_wallet_count(settings)
        max_wallets = wallet_count_data["count"]
        
        # Update all jobs
        updated_count = await scheduler_service.update_all_jobs_wallet_count()
        
        return {
            "success": True,
            "message": f"Updated {updated_count} jobs to use {max_wallets} wallets (max available)",
            "max_wallets": max_wallets,
            "wallet_source": wallet_count_data["source"],
            "jobs_updated": updated_count
        }
        
    except Exception as e:
        logger.error(f"Error updating all jobs wallet counts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status(settings: Settings = Depends(get_settings)):
    """Get overall system status"""
    try:
        logger.info("Fetching system status")
        
        jobs = await scheduler_service.list_jobs()
        
        active_count = sum(1 for job in jobs if job.state.value == "ENABLED")
        paused_count = sum(1 for job in jobs if job.state.value == "PAUSED")
        total_executions = sum(job.execution_count for job in jobs)
        total_successes = sum(job.success_count for job in jobs)
        
        success_rate = (total_successes / total_executions * 100) if total_executions > 0 else 0
        
        # Get current wallet count
        wallet_count_data = await get_wallet_count(settings)
        
        status_data = {
            "total_jobs": len(jobs),
            "active_jobs": active_count,
            "paused_jobs": paused_count,
            "total_executions": total_executions,
            "success_rate": round(success_rate, 1),
            "wallet_count": wallet_count_data["count"],
            "wallet_count_source": wallet_count_data["source"],
            "wallet_count_success": wallet_count_data["success"],
            "app_version": settings.app_version,
            "debug_mode": settings.debug,
            "last_updated": "2025-09-11T12:00:00Z"
        }
        
        logger.info(f"Status retrieved successfully: {len(jobs)} jobs, {wallet_count_data['count']} wallets")
        return status_data
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job-templates")
async def get_job_templates(settings: Settings = Depends(get_settings)):
    """Get predefined job templates with max wallet count"""
    try:
        # Get current wallet count for templates
        wallet_count_data = await get_wallet_count(settings)
        max_wallets = wallet_count_data["count"]
        
        templates = [
            {
                "id": "crypto-buy-analysis-base-optimized",
                "name": "Base Buy Analysis (Optimized)",
                "network": "base", 
                "analysis_type": "buy",
                "schedule": "30 20,21,23,1,5,7,8,10 * * *",
                "num_wallets": max_wallets,
                "description": f"Optimized Base buy analysis using all {max_wallets} wallets"
            },
            {
                "id": "crypto-sell-analysis-base-optimized",
                "name": "Base Sell Analysis (Optimized)",
                "network": "base",
                "analysis_type": "sell", 
                "schedule": "30 20,22,0,3,6,9,11 * * *",
                "num_wallets": max_wallets,
                "description": f"Optimized Base sell analysis using all {max_wallets} wallets"
            },
            {
                "id": "crypto-buy-analysis-ethereum",
                "name": "Ethereum Buy Analysis",
                "network": "ethereum",
                "analysis_type": "buy",
                "schedule": "0 */4 * * *",
                "num_wallets": max_wallets,
                "description": f"Ethereum buy analysis every 4 hours using all {max_wallets} wallets"
            },
            {
                "id": "crypto-sell-analysis-ethereum",
                "name": "Ethereum Sell Analysis", 
                "network": "ethereum",
                "analysis_type": "sell",
                "schedule": "30 */6 * * *",
                "num_wallets": max_wallets,
                "description": f"Ethereum sell analysis every 6 hours using all {max_wallets} wallets"
            }
        ]
        
        return {
            "templates": templates,
            "max_wallets": max_wallets,
            "wallet_source": wallet_count_data["source"]
        }
    except Exception as e:
        logger.error(f"Error getting job templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cron-presets")
async def get_cron_presets():
    """Get common cron expression presets"""
    presets = [
        {"name": "Every 15 minutes", "expression": "*/15 * * * *"},
        {"name": "Every 30 minutes", "expression": "*/30 * * * *"},
        {"name": "Every hour", "expression": "0 * * * *"},
        {"name": "Every 2 hours", "expression": "0 */2 * * *"},
        {"name": "Every 4 hours", "expression": "0 */4 * * *"},
        {"name": "Every 6 hours", "expression": "0 */6 * * *"},
        {"name": "Every 12 hours", "expression": "0 */12 * * *"},
        {"name": "Daily at midnight", "expression": "0 0 * * *"},
        {"name": "Daily at 9 AM", "expression": "0 9 * * *"},
        {"name": "Weekly (Sundays)", "expression": "0 0 * * 0"},
        {"name": "Base Optimized Buy", "expression": "30 20,21,23,1,5,7,8,10 * * *"},
        {"name": "Base Optimized Sell", "expression": "30 20,22,0,3,6,9,11 * * *"},
    ]
    
    return {"presets": presets}

# Debug endpoint
@router.get("/debug")
async def debug_info():
    """Debug endpoint to verify API is working"""
    return {
        "message": "Scheduler API is working!",
        "endpoints": [
            "GET /api/wallets/count",
            "GET /api/jobs", 
            "GET /api/jobs/{job_id}",
            "POST /api/jobs",
            "PUT /api/jobs/{job_id}/schedule",
            "POST /api/jobs/{job_id}/run",
            "POST /api/jobs/{job_id}/pause", 
            "POST /api/jobs/{job_id}/resume",
            "DELETE /api/jobs/{job_id}",
            "POST /api/jobs/pause-all",
            "POST /api/jobs/resume-all", 
            "POST /api/jobs/update-wallet-counts",
            "GET /api/status",
            "GET /api/job-templates",
            "GET /api/cron-presets"
        ],
        "timestamp": "2025-09-11T16:07:00Z"
    }