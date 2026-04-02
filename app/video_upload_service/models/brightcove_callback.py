from pydantic import BaseModel
from typing import Optional


class BrightcoveCallback(BaseModel):
    jobId: str
    status: str
    videoId: Optional[str] = None
    accountId: Optional[str] = None
