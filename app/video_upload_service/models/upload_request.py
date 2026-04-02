from pydantic import BaseModel, field_validator
from typing import Dict
import re

ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/mov",
    "video/quicktime",
    "video/x-m4a",
}

class CreateUploadRequest(BaseModel):
    created_by_user_id: str
    source_surface: str
    file_name: str
    file_size_bytes: int
    content_type: str
    metadata: Dict


    # file name validation
    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, v: str):

        # prevent path injection
        if "/" in v or "\\" in v:
            raise ValueError("Invalid file name")

        # allow only safe chars
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError("File name contains unsupported characters")

        return v

    # file size validation
    @field_validator("file_size_bytes")
    @classmethod
    def validate_size(cls, v: int):

        if v <= 0:
            raise ValueError("file_size_bytes must be greater than zero")

        # optional safety cap (for example 5GB)
        if v > 5 * 1024 * 1024 * 1024:
            raise ValueError("file too large")

        return v

    # Content type governance
    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str):

        if v not in ALLOWED_CONTENT_TYPES:
            raise ValueError("Unsupported content_type")

        return v