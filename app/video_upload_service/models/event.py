from pydantic import BaseModel
from datetime import datetime
from typing import Dict


class UploadEvent(BaseModel):
    id: str
    session_id: str
    timestamp: datetime
    event_type: str
    payload: Dict
