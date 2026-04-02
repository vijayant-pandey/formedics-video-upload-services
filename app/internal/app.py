from fastapi import Depends, FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from security import INTERNAL_APP_API_KEY_VALIDATOR, BACKEND_SERVICES_KEY_VALIDATOR
from common.logging.middleware import RequestLoggingMiddleware
from common.logging.exception_handlers import setup_exception_handlers
from .services.mashup.service import MashupMongoService, UpdateArticleRequest, InsertArticleRequest, MashupImportPayload
from .services.content.service import F1ContentService, SafeImageDetection, GetF1ContentParams, F1ContentOutput, build_f1_content_params
from .services.ga_validation.service import GCSDownloadService
from .services.ga_validation.ga_tracking_rules import tracking_rules
from .services.ump.service import ValidateCampaign, ValidateRequest, ValidateResponse, GetCampaigns, UpdateTargetingResponse, UpdateTargetingRequest, GAMService, Polling


internal_tags_metadata = [
    {
        'name': 'O&O Websites',
        'description': '',
    }, {
        'name': 'Mashupmd.com',
        'description': '',
    }
]

internal_app = FastAPI(openapi_tags=internal_tags_metadata,
                        swagger_ui_parameters={
                            'docExpansion':'none',
                            'defaultModelsExpandDepth': -1
                        })

internal_app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)
internal_app.add_middleware(RequestLoggingMiddleware, service_name='internal')

# Setup exception handlers
setup_exception_handlers(internal_app, service_name='internal')

mashup_mongo_service = MashupMongoService()
f1_content = F1ContentService()
gcs_download = GCSDownloadService()
image_detection = SafeImageDetection()
ump_validation = ValidateCampaign
ump_campaigns = GetCampaigns()
ump_gam = GAMService()
polling = Polling()


@internal_app.post('/mongodb/action/updateOne', tags=['O&O Websites'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
async def update_website_search_article(payload:UpdateArticleRequest):
    '''
    Updates one article into the search articles collection by website.
    '''
    return mashup_mongo_service.update_website_search_article(payload)

@internal_app.post('/mongodb/action/insertOne', tags=['O&O Websites'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
async def insert_website_search_article(payload: InsertArticleRequest):
    '''
    Insert one article into the search articles collection by website.
    '''
    return mashup_mongo_service.insert_website_search_article(payload)

@internal_app.post('/mashup/import-articles', tags=['Mashupmd.com'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def import_mashup_articles(payload: MashupImportPayload):
    '''
    Imports twitter articles from MongoDB to import to mashupmd.com
    '''
    return mashup_mongo_service.import_mashup_articles(payload)

@internal_app.get('/content/f1-content-widget', tags=['Content Retrieval'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def fetch_f1_content(params: GetF1ContentParams = Depends(build_f1_content_params)) -> F1ContentOutput:
    '''
    Retrieves Figure1 content from BigQuery using the provided case UUIDs
    '''
    return f1_content.get_content(params.site.name, params.case_ids.values)

@internal_app.get('/image_safe_detection', tags=['Content Retrieval'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def image_safe_detection(uri: str) -> tuple[bool, dict]:
    '''
    Classifies an image to is_safe true/false
    '''
    return image_detection.is_image_safe(uri=uri)

@internal_app.get('/downloads/fm_ga_validator', tags=['Downloads'])
def download_fm_ga_validator():
    '''
    Downloads the FM GA Validator zip file from GCS bucket
    '''
    return gcs_download.download_file('fm_ga_validator', 'fm_ga_validator')

@internal_app.get('/ga_tracking_rules', tags=['Validation Tracking'])
def get_ga_tracking_test_json():
    '''
    Returns standard rules for use with the Fomedics Tracking Validator Chrome extension
    '''
    return JSONResponse(status_code=200, content=tracking_rules)

@internal_app.post('/ump/validate', tags=['Unified Marketing Platform'], dependencies=[Depends(BACKEND_SERVICES_KEY_VALIDATOR)])
def validate_campaign(body: ValidateRequest) -> ValidateResponse:
    return ump_validation(body)._process()


@internal_app.get('/ump/campaigns', tags=['Unified Marketing Platform'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def list_campaigns(limit: int = Query(50, ge=1, le=500)):
    '''List recent validations, optionally filtered by status.'''
    return JSONResponse(status_code=200, content=ump_campaigns.get_campaign_list(limit))


@internal_app.get('/ump/campaigns/{line_item_id}', tags=['Unified Marketing Platform'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def campaign_details(line_item_id: int):
    '''Return campaign details records for a given line item.'''
    return ump_campaigns.get_campaign_details(line_item_id)


@internal_app.patch('/ump/line_item/targeting', tags=['Unified Marketing Platform'],
                    dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
                    # ,
                    # response_model=UpdateTargetingResponse)
def update_line_item_targeting(body: UpdateTargetingRequest): # still needsd work
    """
    Update the custom targeting segment on a GAM line item (by ID or Name).
    """
    return ump_gam.update_line_item_targeting(body)


@internal_app.get('/ump/create_creative/{line_item_id}', tags=['Unified Marketing Platform'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def campaign_details(line_item_id: int):
    '''For testing only'''
    ump_gam.create_creative(line_item_id)
    return JSONResponse(status_code=200, content='Test')


@internal_app.get('/ump/poll/bigquery', tags=['Unified Marketing Platform'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def polling_bq():
    return polling.poll_bq()


@internal_app.get('/ump/poll/blueconic', tags=['Unified Marketing Platform'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def polling_blueconic():
    return polling.poll_blueconic()


@internal_app.get('/ump/poll/iterable', tags=['Unified Marketing Platform'], dependencies=[Depends(INTERNAL_APP_API_KEY_VALIDATOR)])
def polling_iterable():
    return polling.poll_iterable()
