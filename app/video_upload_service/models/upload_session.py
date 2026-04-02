from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
from enum import Enum


class UploadStatus(str, Enum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    INGESTING = "INGESTING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"

class BrightcoveInfo(BaseModel):
    account_id: Optional[str] = None
    video_id: Optional[str] = None
    job_id: Optional[str] = None


class ErrorInfo(BaseModel):
    code: Optional[str] = None
    message: Optional[str] = None


class UploadSession(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by_user_id: str
    source_surface: str
    status: UploadStatus
    retry_count: int | None = 0
    gcs_bucket: str
    gcs_object_path: str

    file_name: str
    file_size_bytes: int
    content_type: str

    checksum: Optional[str] = None
    metadata: Dict = {}

    brightcove: BrightcoveInfo = BrightcoveInfo()
    error: Optional[ErrorInfo] = None

    expires_at: datetime
    _generation: int | None = None
