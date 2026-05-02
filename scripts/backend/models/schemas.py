from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Message(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: Optional[datetime] = None


class CaseCreate(BaseModel):
    scholar_name: str
    institution: Optional[str] = ""


class CaseResponse(BaseModel):
    case_id: str
    scholar_name: str
    institution: str
    case_dir: str
    phase: str
    created_at: str
    updated_at: str


class ChatRequest(BaseModel):
    message: str
    file_ids: Optional[List[str]] = []


class SSEEvent(BaseModel):
    type: str  # "text" | "agent_status" | "critical" | "done" | "error"
    content: Optional[str] = ""
    agent: Optional[str] = ""
    task: Optional[str] = ""
    state: Optional[str] = ""
    finding: Optional[str] = ""
    confidence: Optional[float] = 0.0
    options: Optional[List[str]] = []
    message: Optional[str] = ""


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    type: str
    saved_path: str


class StatusResponse(BaseModel):
    case_id: str
    phase: str
    active_agents: List[dict]
    recent_completed: List[dict]
    critical_items: List[dict]
    tracked_evidence: List[str]
    message_count: int
