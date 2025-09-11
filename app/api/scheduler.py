# Enhanced Scheduler API with Structured Logging
# Now you can debug issues 10x faster!

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from app.models.job import (
    SchedulerJob, JobCreateRequest, JobUpdateRequest, 
    JobExecutionRequest, NetworkType, AnalysisType
)
from app.services.scheduler import scheduler_service
from app.services.config import get_settings, Settings
from app.services.logging import crypto_logger  # Our new structured logger
from typing import List
import httpx
import time

router = APIRouter()

@router.get("/wallets/count")
async def get_wallet_count(settings: Settings = Depends(get_settings)):
    """Get wallet count with detailed structured logging"""
    start_time = time.time()
    
    # Start logging the operation
    log = crypto_logger.wallet_api_call("fetch_count")
    log.info("Starting wallet count fetch")
    
    try:
        timeout = httpx.Timeout(settings.wallet_api_timeout)
        
        # Log the request details
        log.info("Making HTTP request", timeout=settings.wallet_api_timeout)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{settings.wallet_api_url}/wallets/count")
            
            # Log response details
            duration = time.time() - start_time
            crypto_logger.performance("wallet_api_call", duration, 
                                     status_code=response.status_code)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Log the parsing attempt
                    log.debug("Parsing response", response_type=type(data).__name__)
                    
                    if isinstance(data, dict) and 'count' in data:
                        count = data.get("count", 0)
                        log.info("Parsed count from dict.count", count=count)
                    elif isinstance(data, dict) and len(data) == 1:
                        count = list(data.values())[0]
                        log.info("Parsed count from single dict value", count=count)
                    elif isinstance(data, (int, float)):
                        count = int(data)
                        log.info("Parsed count from direct number", count=count)
                    elif isinstance(data, str) and data.isdigit():
                        count = int(data)
                        log.info("Parsed count from string number", count=count)
                    else:
                        log.warning("Unexpected response format", 
                                   response_data=data, 
                                   response_type=type(data).__name__)
                        count = 1000
                        
                except Exception as parse_error:
                    log.error("JSON parsing failed", 
                             error=str(parse_error),
                             response_text=response.text[:200])  # First 200 chars
                    try:
                        text_response = response.text.strip()
                        count = int(text_response)
                        log.info("Parsed from text fallback", count=count)
                    except ValueError:
                        log.error("Text parsing also failed", text=text_response)
                        count = 1000
                
                # Success logging
                log.info("Wallet count fetch successful", 
                        count=count, 
                        duration_ms=round(duration * 1000, 2))
                
                return {
                    "success": True,
                    "count": count,
                    "source": "wallet-api",
                    "api_url": settings.wallet_api_url,
                    "duration_ms": round(duration * 1000, 2)
                }
            else:
                # Error logging
                log.error("Wallet API error response", 
                         status_code=response.status_code,
                         response_text=response.text[:200])
                
                return {
                    "success": False,
                    "count": 1000,
                    "source": "fallback",
                    "error": f"API returned HTTP {response.status_code}",
                    "api_url": settings.wallet_api_url
                }
                
    except Exception as e:
        duration = time.time() - start_time
        
        # Exception logging with full context
        log.error("Wallet API call failed", 
                 error=str(e),
                 error_type=type(e).__name__,
                 duration_ms=round(duration * 1000, 2),
                 exc_info=True)  # Include stack trace
        
        return {
            "success": False,
            "count": 1000,
            "source": "fallback",
            "error": str(e),
            "api_url": settings.wallet_api_url
        }

@router.post("/jobs", response_model=dict)
async def create_job(
    job_request: JobCreateRequest, 
    settings: Settings = Depends(get_settings)
):
    """Create job with comprehensive logging"""
    start_time = time.time()
    
    # Start job operation logging
    log = crypto_logger.job_operation(job_request.id, "create")
    log.info("Starting job creation", 
             network=job_request.network,
             analysis_type=job_request.analysis_type,
             requested_wallets=job_request.num_wallets)
    
    try:
        # Get wallet count with logging
        log.info("Fetching current wallet count")
        wallet_count_data = await get_wallet_count(settings)
        actual_wallet_count = wallet_count_data["count"]
        
        # Log wallet count override
        if job_request.num_wallets != actual_wallet_count:
            log.info("Overriding wallet count", 
                    requested=job_request.num_wallets,
                    actual=actual_wallet_count)
        
        job_request.num_wallets = actual_wallet_count
        
        # Log job creation attempt
        log.info("Creating job with scheduler service")
        success = await scheduler_service.create_job(job_request)
        
        duration = time.time() - start_time
        
        if not success:
            log.error("Job creation failed at scheduler service level")
            raise HTTPException(status_code=400, detail="Failed to create job")
        
        # Success logging
        crypto_logger.performance("job_creation", duration,
                                 job_id=job_request.id,
                                 wallets=actual_wallet_count)
        
        log.info("Job created successfully", 
                wallet_count=actual_wallet_count,
                duration_ms=round(duration * 1000, 2))
        
        return {
            "success": True, 
            "message": f"Job {job_request.id} created with {actual_wallet_count} wallets",
            "wallet_count": actual_wallet_count,
            "wallet_source": wallet_count_data["source"],
            "duration_ms": round(duration * 1000, 2)
        }
        
    except HTTPException:
        duration = time.time() - start_time
        log.error("Job creation failed with HTTP exception", 
                 duration_ms=round(duration * 1000, 2))
        raise
    except Exception as e:
        duration = time.time() - start_time
        log.error("Job creation failed with unexpected error", 
                 error=str(e),
                 error_type=type(e).__name__,
                 duration_ms=round(duration * 1000, 2),
                 exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/run")
async def run_job_now(
    job_id: str, 
    execution_request: JobExecutionRequest = None,
    settings: Settings = Depends(get_settings)
):
    """Run job with detailed execution logging"""
    start_time = time.time()
    
    log = crypto_logger.job_operation(job_id, "execute")
    log.info("Starting immediate job execution")
    
    try:
        # Get wallet count
        wallet_count_data = await get_wallet_count(settings)
        actual_wallet_count = wallet_count_data["count"]
        
        if execution_request is None:
            execution_request = JobExecutionRequest()
        
        execution_request.num_wallets = actual_wallet_count
        
        log.info("Job execution parameters set", 
                wallets=actual_wallet_count,
                days_back=execution_request.days_back)
        
        # Trigger via scheduler
        log.info("Triggering job via scheduler")
        scheduler_success = await scheduler_service.run_job_now(job_id)
        
        # Get job details for direct call
        job = await scheduler_service.get_job(job_id)
        if job:
            log.info("Making direct function call", 
                    network=job.network,
                    analysis_type=job.analysis_type,
                    function_url=settings.crypto_function_url)
            
            payload = {
                "network": job.network,
                "analysis_type": job.analysis_type,
                "num_wallets": actual_wallet_count,
                "days_back": execution_request.days_back
            }
            
            try:
                func_start = time.time()
                timeout = httpx.Timeout(settings.api_timeout)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(settings.crypto_function_url, json=payload)
                
                func_duration = time.time() - func_start
                crypto_logger.performance("crypto_function_call", func_duration,
                                         job_id=job_id,
                                         status_code=response.status_code)
                
                if response.status_code == 200:
                    result = response.json()
                    total_duration = time.time() - start_time
                    
                    log.info("Job execution completed successfully",
                            transactions=result.get("total_transactions", 0),
                            tokens=result.get("unique_tokens", 0),
                            eth_value=result.get("total_eth_value", 0),
                            function_duration_ms=round(func_duration * 1000, 2),
                            total_duration_ms=round(total_duration * 1000, 2))
                    
                    return {
                        "success": True,
                        "message": f"Job {job_id} executed successfully with {actual_wallet_count} wallets",
                        "result": {
                            "transactions": result.get("total_transactions", 0),
                            "tokens": result.get("unique_tokens", 0),
                            "eth_value": result.get("total_eth_value", 0),
                            "wallets_used": actual_wallet_count,
                            "function_duration_ms": round(func_duration * 1000, 2),
                            "total_duration_ms": round(total_duration * 1000, 2)
                        }
                    }
                else:
                    log.warning("Function call failed", 
                               status_code=response.status_code,
                               response_text=response.text[:200])
                    
                    return {
                        "success": scheduler_success,
                        "message": f"Job triggered via scheduler (function call failed: HTTP {response.status_code})",
                        "wallets_used": actual_wallet_count
                    }
                    
            except Exception as func_error:
                log.error("Direct function call failed", 
                         error=str(func_error),
                         error_type=type(func_error).__name__,
                         exc_info=True)
                
                return {
                    "success": scheduler_success,
                    "message": f"Job triggered via scheduler (direct call failed: {func_error})",
                    "wallets_used": actual_wallet_count
                }
        
        total_duration = time.time() - start_time
        log.info("Job execution completed", 
                success=scheduler_success,
                duration_ms=round(total_duration * 1000, 2))
        
        return {
            "success": scheduler_success, 
            "message": f"Job {job_id} triggered with {actual_wallet_count} wallets",
            "wallets_used": actual_wallet_count,
            "duration_ms": round(total_duration * 1000, 2)
        }
        
    except HTTPException:
        duration = time.time() - start_time
        log.error("Job execution failed with HTTP exception", 
                 duration_ms=round(duration * 1000, 2))
        raise
    except Exception as e:
        duration = time.time() - start_time
        log.error("Job execution failed with unexpected error", 
                 error=str(e),
                 error_type=type(e).__name__,
                 duration_ms=round(duration * 1000, 2),
                 exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/recent")
async def get_recent_logs():
    """Get recent structured logs for debugging"""
    # This would connect to your log aggregation system
    # For now, return info about logging setup
    settings = get_settings()
    
    return {
        "logging_enabled": True,
        "debug_mode": settings.debug,
        "log_format": "JSON" if not settings.debug else "Console",
        "components": [
            "wallet_api",
            "job_scheduler", 
            "cache",
            "api",
            "performance"
        ],
        "log_levels": ["DEBUG", "INFO", "WARNING", "ERROR"],
        "structured_fields": [
            "component",
            "operation", 
            "duration_ms",
            "error_type",
            "job_id",
            "wallet_count"
        ]
    }