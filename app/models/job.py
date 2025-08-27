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
