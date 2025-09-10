from pydantic import BaseModel, Field
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
    # Changed: num_wallets now defaults to 0, which signals to use max available
    num_wallets: int = Field(default=0, description="Number of wallets to use (0 = use all available)")
    days_back: float = 1.0

    class Config:
        json_schema_extra = {
            "example": {
                "id": "crypto-buy-analysis-base",
                "name": "Base Buy Analysis",
                "network": "base",
                "analysis_type": "buy", 
                "schedule": "0 */4 * * *",
                "description": "Analyzes buy transactions on Base network",
                "num_wallets": 0,  # 0 means use all available
                "days_back": 1.0
            }
        }

class JobUpdateRequest(BaseModel):
    schedule: Optional[str] = None
    description: Optional[str] = None
    # Changed: num_wallets defaults to 0 (use max) when updating
    num_wallets: Optional[int] = Field(default=0, description="Number of wallets to use (0 = use all available)")
    days_back: Optional[float] = None

class JobExecutionRequest(BaseModel):
    # Changed: Default to 0 which means use all available wallets
    num_wallets: int = Field(default=0, description="Number of wallets to use for this execution (0 = use all available)")
    days_back: float = 1.0
