from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
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

@router.get("/wallets/count")
async def get_wallet_count(settings: Settings = Depends(get_settings)):
    """Get the current wallet count from the wallet API using config settings"""
    try:
        timeout = httpx.Timeout(settings.wallet_api_timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{settings.wallet_api_url}/wallets/count")
            
            if response.status_code == 200:
                # Handle different response formats
                try:
                    data = response.json()
                    
                    # Case 1: Response is a JSON object with 'count' field
                    if isinstance(data, dict) and 'count' in data:
                        count = data.get("count", 0)
                    # Case 2: Response is a JSON object with direct number
                    elif isinstance(data, dict) and len(data) == 1:
                        # Get the first (and only) value from the dict
                        count = list(data.values())[0]
                    # Case 3: Response is just a number
                    elif isinstance(data, (int, float)):
                        count = int(data)
                    # Case 4: Response is a string that can be converted to int
                    elif isinstance(data, str) and data.isdigit():
                        count = int(data)
                    else:
                        logger.warning(f"Unexpected wallet API response format: {data}")
                        count = 1000  # Fallback
                        
                except Exception as parse_error:
                    # If JSON parsing fails, try to parse as plain text
                    logger.warning(f"JSON parsing failed: {parse_error}")
                    try:
                        text_response = response.text.strip()
                        count = int(text_response)
                    except ValueError:
                        logger.error(f"Could not parse wallet count from: {text_response}")
                        count = 1000  # Fallback
                
                logger.info(f"Successfully retrieved wallet count: {count}")
                return {
                    "success": True,
                    "count": count,
                    "source": "wallet-api",
                    "api_url": settings.wallet_api_url,
                    "timeout_used": settings.wallet_api_timeout
                }
            else:
                logger.error(f"Wallet API returned HTTP {response.status_code}")
                return {
                    "success": False,
                    "count": 1000,  # Fallback value
                    "source": "fallback",
                    "error": f"API returned HTTP {response.status_code}",
                    "api_url": settings.wallet_api_url
                }
                
    except Exception as e:
        logger.error(f"Error fetching wallet count: {e}")
        return {
            "success": False,
            "count": 1000,  # Fallback value
            "source": "fallback",
            "error": str(e),
            "api_url": settings.wallet_api_url
        }

@router.get("/config")
async def get_config_info(settings: Settings = Depends(get_settings)):
    """Get current configuration (safe values only)"""
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
        # Don't expose sensitive values like secret_key or admin_password
    }

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
async def create_job(
    job_request: JobCreateRequest, 
    settings: Settings = Depends(get_settings)
):
    """Create a new scheduler job - ALWAYS uses max available wallets"""
    try:
        # ALWAYS get the current max wallet count - ignore any provided value
        wallet_count_data = await get_wallet_count(settings)
        actual_wallet_count = wallet_count_data["count"]
        
        # Override any provided num_wallets with the current max
        job_request.num_wallets = actual_wallet_count
        
        logger.info(f"Creating job {job_request.id} with {actual_wallet_count} wallets (max available)")
        
        success = await scheduler_service.create_job(job_request)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create job")
        
        return {
            "success": True, 
            "message": f"Job {job_request.id} created successfully with {actual_wallet_count} wallets (max available)",
            "wallet_count": actual_wallet_count,
            "wallet_source": wallet_count_data["source"],
            "config_used": {
                "crypto_function_url": settings.crypto_function_url,
                "timeout": settings.api_timeout
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/run")
async def run_job_now(
    job_id: str, 
    execution_request: JobExecutionRequest = None,
    settings: Settings = Depends(get_settings)
):
    """Run a job immediately with max wallets"""
    try:
        # ALWAYS use max wallets for immediate execution
        wallet_count_data = await get_wallet_count(settings)
        actual_wallet_count = wallet_count_data["count"]
        
        # Create execution request with max wallets if not provided
        if execution_request is None:
            execution_request = JobExecutionRequest()
        
        # Always override with max wallet count
        execution_request.num_wallets = actual_wallet_count
        
        logger.info(f"Running job {job_id} immediately with {actual_wallet_count} wallets (max available)")
        
        # First trigger via scheduler
        scheduler_success = await scheduler_service.run_job_now(job_id)
        
        # Also call the function directly for immediate feedback
        job = await scheduler_service.get_job(job_id)
        if job:
            payload = {
                "network": job.network,
                "analysis_type": job.analysis_type,
                "num_wallets": actual_wallet_count,  # Use actual max count
                "days_back": execution_request.days_back
            }
            
            try:
                timeout = httpx.Timeout(settings.api_timeout)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(settings.crypto_function_url, json=payload)
                    
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "message": f"Job {job_id} executed successfully with {actual_wallet_count} wallets (max available)",
                        "result": {
                            "transactions": result.get("total_transactions", 0),
                            "tokens": result.get("unique_tokens", 0),
                            "eth_value": result.get("total_eth_value", 0),
                            "wallets_used": actual_wallet_count,
                            "wallet_source": wallet_count_data["source"]
                        },
                        "config_used": {
                            "function_url": settings.crypto_function_url,
                            "timeout": settings.api_timeout
                        }
                    }
                else:
                    return {
                        "success": scheduler_success,
                        "message": f"Job {job_id} triggered via scheduler with {actual_wallet_count} wallets (function call failed: HTTP {response.status_code})",
                        "wallets_used": actual_wallet_count
                    }
                    
            except Exception as func_error:
                logger.warning(f"Direct function call failed: {func_error}")
                return {
                    "success": scheduler_success,
                    "message": f"Job {job_id} triggered via scheduler with {actual_wallet_count} wallets (direct call failed)",
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
            "jobs_updated": updated_count,
            "config_used": {
                "wallet_api_url": settings.wallet_api_url,
                "timeout": settings.wallet_api_timeout
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating all jobs wallet counts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status(settings: Settings = Depends(get_settings)):
    """Get overall system status"""
    try:
        jobs = await scheduler_service.list_jobs()
        
        active_count = sum(1 for job in jobs if job.state.value == "ENABLED")
        paused_count = sum(1 for job in jobs if job.state.value == "PAUSED")
        total_executions = sum(job.execution_count for job in jobs)
        total_successes = sum(job.success_count for job in jobs)
        
        success_rate = (total_successes / total_executions * 100) if total_executions > 0 else 0
        
        # Get current wallet count
        wallet_count_data = await get_wallet_count(settings)
        
        return {
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
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job-templates")
async def get_job_templates(settings: Settings = Depends(get_settings)):
    """Get predefined job templates with max wallet count and optimized schedules"""
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
                "num_wallets": max_wallets,  # Always use max
                "description": f"Optimized Base buy analysis using all {max_wallets} wallets"
            },
            {
                "id": "crypto-sell-analysis-base-optimized",
                "name": "Base Sell Analysis (Optimized)",
                "network": "base",
                "analysis_type": "sell", 
                "schedule": "30 20,22,0,3,6,9,11 * * *",
                "num_wallets": max_wallets,  # Always use max
                "description": f"Optimized Base sell analysis using all {max_wallets} wallets"
            },
            {
                "id": "crypto-buy-analysis-ethereum",
                "name": "Ethereum Buy Analysis",
                "network": "ethereum",
                "analysis_type": "buy",
                "schedule": "0 */4 * * *",
                "num_wallets": max_wallets,  # Always use max
                "description": f"Ethereum buy analysis every 4 hours using all {max_wallets} wallets"
            },
            {
                "id": "crypto-sell-analysis-ethereum",
                "name": "Ethereum Sell Analysis", 
                "network": "ethereum",
                "analysis_type": "sell",
                "schedule": "30 */6 * * *",
                "num_wallets": max_wallets,  # Always use max
                "description": f"Ethereum sell analysis every 6 hours using all {max_wallets} wallets"
            }
        ]
        
        return {
            "templates": templates,
            "max_wallets": max_wallets,
            "wallet_source": wallet_count_data["source"],
            "function_url": settings.crypto_function_url
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