from typing import List, Optional
from pydantic import BaseModel, HttpUrl, field_validator
from fastapi import HTTPException, Query
import re
from enum import Enum


class F1ContentOriginatingSite(BaseModel):
    name: str

    @field_validator('name')
    def validate_site(cls, v):
        if not re.fullmatch(r'^(?!_)[a-z_]+$', v):
            raise HTTPException(status_code=422,
                                detail='site must contain only lowercase letters and underscores, no spaces or numbers')
        return v

class CommaSeparatedUUIDv4(BaseModel):
    values: str

    @field_validator('values')
    def uuids_must_be_comma_separated_uuidv4(cls, v):
        UUID_V4_REGEX = r'^([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})(,([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}))*$'
        if not re.fullmatch(UUID_V4_REGEX, v):
            raise HTTPException(status_code=422,
                                detail='String is not a valid comma-separated list of UUID v4 values, no spaces')
        return v

class GetF1ContentParams(BaseModel):
    site: F1ContentOriginatingSite
    case_ids: CommaSeparatedUUIDv4

def build_f1_content_params(
    site: str = Query(..., description='Site name'),
    case_ids: str = Query(..., description='Comma-separated UUIDs')
) -> GetF1ContentParams:
    return GetF1ContentParams(
        site=F1ContentOriginatingSite(name=site),
        case_ids=CommaSeparatedUUIDv4(values=case_ids)
    )

class F1ImageDetectionEnum(str, Enum):
    UNKNOWN = 'UNKNOWN'
    VERY_UNLIKELY = 'VERY_UNLIKELY'
    UNLIKELY = 'UNLIKELY'
    POSSIBLE =  'POSSIBLE'
    LIKELY = 'LIKELY'
    VERY_LIKELY = 'VERY_LIKELY'

class F1ImageDetection(BaseModel):
    adult: F1ImageDetectionEnum
    violence: F1ImageDetectionEnum
    # racy: F1ImageDetectionEnum
    # medical: F1ImageDetectionEnum

class F1ContentInfo(BaseModel):
    site_nm: str
    case_ids: str

class F1ContentOutputBase(BaseModel):
    case_id: str
    title: Optional[str] = None
    image_url: List[HttpUrl]
    teaser: Optional[str] = None
    cta_url: HttpUrl

class SafeImageResults(BaseModel):
    image: str
    is_safe: bool
    is_safe_results: F1ImageDetection

class F1ContentOutputFixed(F1ContentOutputBase):
    image_results: List[SafeImageResults]

class F1ContentOutput(BaseModel):
    cases: List[F1ContentOutputFixed]
