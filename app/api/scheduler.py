from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.job import (
    SchedulerJob, JobCreateRequest, JobUpdateRequest, 
    JobExecutionRequest, NetworkType, AnalysisType
)
from app.services.scheduler import scheduler_service
from typing import List
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/jobs", response_model=List[SchedulerJob])
async def list_jobs():
    """Get all scheduler jobs"""
    try:
        jobs = await scheduler_service.list_jobs()
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
async def create_job(job_request: JobCreateRequest):
    """Create a new scheduler job"""
    try:
        success = await scheduler_service.create_job(job_request)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create job")
        
        return {"success": True, "message": f"Job {job_request.id} created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
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

@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str, execution_request: JobExecutionRequest = JobExecutionRequest()):
    """Run a job immediately"""
    try:
        # First trigger via scheduler
        scheduler_success = await scheduler_service.run_job_now(job_id)
        
        # Also call the function directly for immediate feedback
        job = await scheduler_service.get_job(job_id)
        if job:
            payload = {
                "network": job.network,
                "analysis_type": job.analysis_type,
                "num_wallets": execution_request.num_wallets,
                "days_back": execution_request.days_back
            }
            
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(job.function_url, json=payload)
                    
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "message": f"Job {job_id} executed successfully",
                        "result": {
                            "transactions": result.get("total_transactions", 0),
                            "tokens": result.get("unique_tokens", 0),
                            "eth_value": result.get("total_eth_value", 0)
                        }
                    }
                else:
                    return {
                        "success": scheduler_success,
                        "message": f"Job {job_id} triggered via scheduler (function call failed: HTTP {response.status_code})"
                    }
                    
            except Exception as func_error:
                logger.warning(f"Direct function call failed: {func_error}")
                return {
                    "success": scheduler_success,
                    "message": f"Job {job_id} triggered via scheduler (direct call failed)"
                }
        
        return {"success": scheduler_success, "message": f"Job {job_id} triggered"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running job {job_id}: {e}")
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

@router.get("/status")
async def get_status():
    """Get overall system status"""
    try:
        jobs = await scheduler_service.list_jobs()
        
        active_count = sum(1 for job in jobs if job.state.value == "ENABLED")
        paused_count = sum(1 for job in jobs if job.state.value == "PAUSED")
        total_executions = sum(job.execution_count for job in jobs)
        total_successes = sum(job.success_count for job in jobs)
        
        success_rate = (total_successes / total_executions * 100) if total_executions > 0 else 0
        
        return {
            "total_jobs": len(jobs),
            "active_jobs": active_count,
            "paused_jobs": paused_count,
            "total_executions": total_executions,
            "success_rate": round(success_rate, 1),
            "last_updated": "2025-08-27T12:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job-templates")
async def get_job_templates():
    """Get predefined job templates"""
    templates = [
        {
            "id": "crypto-buy-analysis-ethereum",
            "name": "Ethereum Buy Analysis",
            "network": "ethereum",
            "analysis_type": "buy",
            "schedule": "0 */4 * * *",
            "description": "Analyzes buy transactions on Ethereum network every 4 hours"
        },
        {
            "id": "crypto-sell-analysis-ethereum",
            "name": "Ethereum Sell Analysis", 
            "network": "ethereum",
            "analysis_type": "sell",
            "schedule": "30 */6 * * *",
            "description": "Analyzes sell transactions on Ethereum network every 6 hours"
        },
        {
            "id": "crypto-buy-analysis-base",
            "name": "Base Buy Analysis",
            "network": "base", 
            "analysis_type": "buy",
            "schedule": "15 */4 * * *",
            "description": "Analyzes buy transactions on Base network every 4 hours"
        },
        {
            "id": "crypto-sell-analysis-base",
            "name": "Base Sell Analysis",
            "network": "base",
            "analysis_type": "sell",
            "schedule": "45 */6 * * *",
            "description": "Analyzes sell transactions on Base network every 6 hours"
        }
    ]
    
    return {"templates": templates}

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
    ]
    
    return {"presets": presets}