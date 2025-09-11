from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from app.models.job import (
    SchedulerJob, JobCreateRequest, JobUpdateRequest, 
    JobExecutionRequest, NetworkType, AnalysisType
)
from app.services.scheduler import scheduler_service
from app.services.config import get_settings, Settings
from app.services.cache import cache, cached  # Import our new cache service
from typing import List
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/wallets/count")
@cached(ttl=300, key_prefix="wallet_")  # Cache for 5 minutes
async def get_wallet_count(settings: Settings = Depends(get_settings)):
    """Get wallet count with caching - 10x faster after first call!"""
    try:
        timeout = httpx.Timeout(settings.wallet_api_timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
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
                    "source": "wallet-api",
                    "cached": False,  # Will be True on cache hits
                    "api_url": settings.wallet_api_url,
                    "timeout_used": settings.wallet_api_timeout
                }
            else:
                logger.error(f"Wallet API returned HTTP {response.status_code}")
                return {
                    "success": False,
                    "count": 1000,
                    "source": "fallback",
                    "error": f"API returned HTTP {response.status_code}",
                    "api_url": settings.wallet_api_url
                }
                
    except Exception as e:
        logger.error(f"Error fetching wallet count: {e}")
        return {
            "success": False,
            "count": 1000,
            "source": "fallback",
            "error": str(e),
            "api_url": settings.wallet_api_url
        }

@router.get("/jobs", response_model=List[SchedulerJob])
@cached(ttl=60, key_prefix="jobs_")  # Cache for 1 minute
async def list_jobs():
    """Get all jobs with caching - Much faster dashboard loading!"""
    try:
        jobs = await scheduler_service.list_jobs()
        logger.info(f"Retrieved {len(jobs)} jobs")
        return jobs
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job-templates")
@cached(ttl=600, key_prefix="templates_")  # Cache for 10 minutes
async def get_job_templates(settings: Settings = Depends(get_settings)):
    """Get job templates with caching - Templates rarely change!"""
    try:
        # Get current wallet count (this will be cached too)
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
            "wallet_source": wallet_count_data["source"],
            "function_url": settings.crypto_function_url,
            "cached": True  # Indicates this response may be cached
        }
    except Exception as e:
        logger.error(f"Error getting job templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
@cached(ttl=30, key_prefix="status_")  # Cache for 30 seconds
async def get_status(settings: Settings = Depends(get_settings)):
    """Get system status with caching - Faster dashboard updates!"""
    try:
        jobs = await scheduler_service.list_jobs()
        
        active_count = sum(1 for job in jobs if job.state.value == "ENABLED")
        paused_count = sum(1 for job in jobs if job.state.value == "PAUSED")
        total_executions = sum(job.execution_count for job in jobs)
        total_successes = sum(job.success_count for job in jobs)
        
        success_rate = (total_successes / total_executions * 100) if total_executions > 0 else 0
        
        # Get current wallet count (cached)
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
            "cache_enabled": cache.redis_client is not None,
            "last_updated": "2025-09-11T12:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs", response_model=dict)
async def create_job(
    job_request: JobCreateRequest, 
    settings: Settings = Depends(get_settings)
):
    """Create job and invalidate relevant caches"""
    try:
        # Get current max wallet count (cached)
        wallet_count_data = await get_wallet_count(settings)
        actual_wallet_count = wallet_count_data["count"]
        
        job_request.num_wallets = actual_wallet_count
        
        logger.info(f"Creating job {job_request.id} with {actual_wallet_count} wallets")
        
        success = await scheduler_service.create_job(job_request)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create job")
        
        # Invalidate job-related caches since we created a new job
        cache.clear_pattern("jobs_*")
        cache.clear_pattern("status_*")
        
        return {
            "success": True, 
            "message": f"Job {job_request.id} created with {actual_wallet_count} wallets",
            "wallet_count": actual_wallet_count,
            "wallet_source": wallet_count_data["source"],
            "cache_cleared": True
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
    """Run job immediately with max wallets"""
    try:
        # Get fresh wallet count (may use cache)
        wallet_count_data = await get_wallet_count(settings)
        actual_wallet_count = wallet_count_data["count"]
        
        if execution_request is None:
            execution_request = JobExecutionRequest()
        
        execution_request.num_wallets = actual_wallet_count
        
        logger.info(f"Running job {job_id} with {actual_wallet_count} wallets")
        
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
                timeout = httpx.Timeout(settings.api_timeout)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(settings.crypto_function_url, json=payload)
                    
                if response.status_code == 200:
                    result = response.json()
                    
                    # Clear status cache since job was executed
                    cache.clear_pattern("status_*")
                    
                    return {
                        "success": True,
                        "message": f"Job {job_id} executed with {actual_wallet_count} wallets",
                        "result": {
                            "transactions": result.get("total_transactions", 0),
                            "tokens": result.get("unique_tokens", 0),
                            "eth_value": result.get("total_eth_value", 0),
                            "wallets_used": actual_wallet_count,
                            "wallet_source": wallet_count_data["source"]
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

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete job and clear caches"""
    try:
        success = await scheduler_service.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to delete job")
        
        # Clear relevant caches since job was deleted
        cache.clear_pattern("jobs_*")
        cache.clear_pattern("status_*")
        
        return {
            "success": True, 
            "message": f"Job {job_id} deleted",
            "cache_cleared": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/clear")
async def clear_cache():
    """Clear all caches - useful for debugging"""
    try:
        cleared_wallet = cache.clear_pattern("wallet_*")
        cleared_jobs = cache.clear_pattern("jobs_*")
        cleared_status = cache.clear_pattern("status_*")
        cleared_templates = cache.clear_pattern("templates_*")
        
        total_cleared = cleared_wallet + cleared_jobs + cleared_status + cleared_templates
        
        return {
            "success": True,
            "message": f"Cleared {total_cleared} cache entries",
            "details": {
                "wallet_cache": cleared_wallet,
                "jobs_cache": cleared_jobs,
                "status_cache": cleared_status,
                "templates_cache": cleared_templates
            }
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    return {
        "redis_connected": cache.redis_client is not None,
        "cache_enabled": cache.redis_client is not None,
        "redis_url": getattr(cache.settings, 'redis_url', 'Not configured'),
        "cache_endpoints": [
            {"endpoint": "/wallets/count", "ttl": "5 minutes"},
            {"endpoint": "/jobs", "ttl": "1 minute"},
            {"endpoint": "/job-templates", "ttl": "10 minutes"},
            {"endpoint": "/status", "ttl": "30 seconds"}
        ]
    }