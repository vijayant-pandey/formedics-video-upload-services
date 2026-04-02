from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, UUID4, field_validator, AwareDatetime
from datetime import datetime, timezone


class IterableGeneralResponse(BaseModel):
    msg: str
    code: str
    params: dict


class IterableRecipientTimeZone(BaseModel):
    defaultTimeZone: str
    startTimeZone: str


class IterableScheduleCampaign(BaseModel):
    recipientTimeZone: Optional[IterableRecipientTimeZone] = None
    sendAt: str # 2007-12-03T10:15:30.00Z


class IterableCampaignRequest(BaseModel):
    campaignDataFields: Optional[Dict[str, str]] = None
    dataFields: Optional[Dict[str, str]] = None
    defaultTimeZone: Optional[str] = None # Format: YYYY-MM-DD HH:MM:SS (UTC)
    listIds: List[int]
    name: str
    sendAt: Optional[str] = None
    sendMode: Optional[str] = None
    startTimeZone: Optional[str] = None
    suppressionListIds: Optional[List[int]] = None
    templateId: int


class IterableCreateCampaignResp(BaseModel):
    campaign_id: int = Field(alias='campaignId')


class IterableCampaignDetails(BaseModel):
    id: int
    createdAt: int
    updatedAt: int
    startAt: int
    name: str
    templateId: int
    messageMedium: str
    createdByUserId: str
    updatedByUserId: str
    campaignState: str
    listIds: List[int]
    suppressionListIds: List[int]
    sendSize: int
    recurringCampaignId: int
    labels: List[str]
    type: str


class IterableListsResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    createdAt: int
    list_type: str = Field(alias='listType')
    list_size: Optional[int] = None


class BlueconicTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class User(BaseModel):                                                                                                                                                      
    full_name: str = Field(alias='fullName')
    user_name: str = Field(alias='userName')


class BlueconicSegment(BaseModel):
    can_delete: bool = Field(alias='canDelete')
    creation_date: datetime = Field(alias='creationDate')
    creator: User
    description: str
    favorite: bool
    id: UUID4
    inverse_of: str = Field(alias='inverseOf')
    inversed_by: str = Field(alias='inversedBy')
    last_modified_date: datetime = Field(alias='lastModifiedDate')
    last_modified_user: User = Field(alias='lastModifiedUser')
    name: str
    profile_count: int = Field(alias='profileCount')
    read_only: bool = Field(alias='readOnly')
    tags: list[str]

    model_config = { 'populate_by_name': True }


class BlueconicValidationResponse(BaseModel):
    status: Literal['invalid','valid']
    errors: Optional[str] = None
    segments: List[BlueconicSegment]


def _word_count(text: str) -> int:
    return len(text.split())

### MAIN SCHEMA ###
class CampaignMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    line_item_id: int = Field(alias='LineItemID')
    creative_id: int = Field(alias='CreativeID')
    native_driver_title_text: str
    native_driver_content_text: str
    logo_image: str
    logo_image_url: HttpUrl
    logotype_image: str
    button_1_text: str
    button_1_link: HttpUrl
    button_2_text: Optional[str | None] = None
    button_2_link: Optional[HttpUrl | None] = None
    button_3_text: Optional[str | None] = None
    button_3_link: Optional[HttpUrl | None] = None
    title_text: str
    content_text_1: str
    content_image_1: HttpUrl
    content_text_2: Optional[str | None] = None
    content_image_2: Optional[HttpUrl | None] = None
    content_text_3: Optional[str | None] = None
    content_image_3: Optional[HttpUrl | None] = None
    content_text_4: Optional[str | None] = None
    content_image_4: Optional[HttpUrl | None] = None
    annotation: Optional[str | None] = None
    scrolling_isi_title: str = Field(alias='ScrollingISITitle')
    scrolling_isi_content: str = Field(alias='ScrollingISI')
    footer_text: Optional[str | None] = None
    boostr_deal_id: int
    boostr_deal_name: str
    line_item_name: Optional[str | None] = None
    file_id: Optional[int | None] = None
    dw_ingested_at: AwareDatetime
    blueconic: Optional[BlueconicValidationResponse] = None

    ### MAX WORDS ###
    @field_validator('native_driver_title_text')
    @classmethod
    def native_driver_title_max_words(cls, v: str) -> str:
        if _word_count(v) > 5:
            raise ValueError('Native driver title text must be 5 words or fewer.')
        return v

    @field_validator('button_1_text')
    @classmethod
    def button_1_text_max_words(cls, v: str) -> str:
        if _word_count(v) > 5:
            raise ValueError('Button 1 text must be 5 words or fewer.')
        return v

    @field_validator('button_2_text')
    @classmethod
    def button_2_text_max_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _word_count(v) > 5:
            raise ValueError('Button 2 text must be 5 words or fewer.')
        return v

    @field_validator('button_3_text')
    @classmethod
    def button_3_text_max_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _word_count(v) > 5:
            raise ValueError('Button 3 text must be 5 words or fewer.')
        return v

    @field_validator('title_text')
    @classmethod
    def title_text_max_words(cls, v: str) -> str:
        if _word_count(v) > 15:
            raise ValueError('Title text must be 15 words or fewer.')
        return v

    @field_validator('scrolling_isi_title')
    @classmethod
    def scrolling_isi_title_max_words(cls, v: str) -> str:
        if _word_count(v) > 5:
            raise ValueError('Scrolling ISI title must be 5 words or fewer.')
        return v

    @field_validator('boostr_deal_name')
    @classmethod
    def boostr_deal_name_max_words(cls, v: str) -> str:
        if _word_count(v) > 5:
            raise ValueError('Boostr deal name must be 5 words or fewer.')
        return v

    @field_validator('line_item_name')
    @classmethod
    def line_item_name_max_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _word_count(v) > 5:
            raise ValueError('Line item name must be 5 words or fewer.')
        return v
    
    ### MIN WORDS ###
    @field_validator('native_driver_content_text')
    @classmethod
    def native_driver_content_min_words(cls, v: str) -> str:
        if _word_count(v) < 25:
            raise ValueError('Native driver content text must be at least 25 words.')
        return v

    @field_validator('content_text_1')
    @classmethod
    def content_text_1_min_words(cls, v: str) -> str:
        if _word_count(v) < 25:
            raise ValueError('Content text 1 must be at least 25 words.')
        return v

    @field_validator('content_text_2')
    @classmethod
    def content_text_2_min_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _word_count(v) < 25:
            raise ValueError('Content text 2 must be at least 25 words.')
        return v

    @field_validator('content_text_3')
    @classmethod
    def content_text_3_min_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _word_count(v) < 25:
            raise ValueError('Content text 3 must be at least 25 words.')
        return v

    @field_validator('content_text_4')
    @classmethod
    def content_text_4_min_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _word_count(v) < 25:
            raise ValueError('Content text 4 must be at least 25 words.')
        return v

    @field_validator('annotation')
    @classmethod
    def annotation_min_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _word_count(v) < 10:
            raise ValueError('Annotation must be at least 10 words.')
        return v

    @field_validator('scrolling_isi_content')
    @classmethod
    def scrolling_isi_content_min_words(cls, v: str) -> str:
        if _word_count(v) < 25:
            raise ValueError('Scrolling ISI content must be at least 25 words.')
        return v

    @field_validator('footer_text')
    @classmethod
    def footer_text_min_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _word_count(v) < 25:
            raise ValueError('Footer text must be at least 25 words.')
        return v
    
    @field_validator('dw_ingested_at', mode='before')
    @classmethod
    def assume_utc(cls, v):
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        return v


### HELPER TYPES ###
class SchemaField(BaseModel):
    name: str
    type: str


class BigQuerySchema(BaseModel):
    fields: list[SchemaField]


class BigQueryRow(BaseModel):
    f: list[dict]


# class ValidateRequest(BaseModel):
#     schema_: BigQuerySchema = Field(alias='schema')
#     rows: list[BigQueryRow]
#     # triggered_by: str = 'unknown'


class ValidateRequest(BaseModel):
    rows: list[dict]


class ValidationError_(BaseModel):
    field: str
    message: str


class RowResult(BaseModel):
    line_item_id: Optional[int] = None
    status: str
    errors: list[ValidationError_]


class ValidateResponse(BaseModel):
    total: int
    valid: int
    invalid: int
    results: list[RowResult]


class CampaignList(BaseModel):
    id: str
    creative_id: str
    line_item_id: int


# class GetCampaignListParams(BaseModel):
#     status: Optional[str] = Query(None, pattern='^(valid|invalid)$'),
#     limit: int = Query(50, ge=1, le=500)

# def build_campaign_list_params(
#     status: Optional[str] = Query(None, pattern='^(valid|invalid)$'),
#     limit: int = Query(50, ge=1, le=500)
# ) -> GetCampaignListParams:
#     return GetCampaignListParams(
#         status=Query(None, pattern='^(valid|invalid)$'),
#         limit=Query(50, ge=1, le=500)
#     )


# ── GAM targeting models & endpoint ──────────────────────────────────────

class CustomCriterion(BaseModel):
    key_id: int
    value_ids: list[int]
    operator: str = 'IS'  # IS | IS_NOT


class UpdateTargetingRequest(BaseModel):
    criteria: list[CustomCriterion]
    logical_operator: str = 'OR'  # top-level logical operator: OR | AND
    mode: Literal['replace', 'append'] = 'append'
    append_operator: str = 'AND'  # logical operator when combining existing + new targeting: OR | AND
    line_item_name: Optional[str] = None
    line_item_id: Optional[str] = None


class UpdateTargetingResponse(BaseModel):
    line_item_id: int
    name: str
    custom_targeting: dict


# class UpdateTargeting(UpdateTargetingRequest):
#     """Extends UpdateTargetingRequest with a line item name field."""
#     line_item_name: Optional[str] = None
#     line_item_id: Optional[str] = None


class TemplateVariable(BaseModel):
    type: str          # AssetCreativeTemplateVariableValue | LongCreativeTemplateVariableValue
                       # | UrlCreativeTemplateVariableValue | StringCreativeTemplateVariableValue
    unique_name: str
    value: Optional[str] = None          # for Long, Url, String types
    asset_file_name: Optional[str] = None  # for Asset type
    asset_byte_array: Optional[str] = None # base64-encoded image bytes for Asset type
    asset_width: Optional[int] = None
    asset_height: Optional[int] = None


class CreateTemplateCreativeRequest(BaseModel):
    advertiser_id: int
    creative_template_id: int
    name: str
    width: int
    height: int
    template_variables: list[TemplateVariable]


class CreateTemplateCreativeResponse(BaseModel):
    creative_id: int
    name: str
    creative_type: str



#######

class BaseTemplateVariable(BaseModel):
    uniqueName: str
    xsi_type: str

class StringVariable(BaseTemplateVariable):
    xsi_type: str = "StringCreativeTemplateVariableValue"
    value: str

class UrlVariable(BaseTemplateVariable):
    xsi_type: str = "UrlCreativeTemplateVariableValue"
    value: str

class LongVariable(BaseTemplateVariable):
    xsi_type: str = "LongCreativeTemplateVariableValue"
    value: int

class CreativeAsset(BaseModel):
    fileName: str
    assetByteArray: Optional[bytes] = None # Only needed for upload
    assetId: Optional[int] = None          # Returned by GAM

class AssetVariable(BaseTemplateVariable):
    xsi_type: str = "AssetCreativeTemplateVariableValue"
    asset: CreativeAsset

# Use a Union for the variable list to handle different types
TemplateVariable = Union[StringVariable, UrlVariable, LongVariable, AssetVariable]

# 2. The Main Creative Model
class CreativeSize(BaseModel):
    width: int
    height: int

class TemplateCreativeModel(BaseModel):
    name: str
    advertiserId: int
    creativeTemplateId: int
    size: CreativeSize
    creativeTemplateVariableValues: List[TemplateVariable]
    
    id: Optional[int] = None
    status: Optional[str] = None
    xsi_type: str = 'TemplateCreative'

    class Config:
        from_attributes = True