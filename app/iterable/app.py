from fastapi import Depends, FastAPI, Query
from .dtypes import *
from .services import *
from fastapi.middleware.cors import CORSMiddleware
from security import ITERABLE_APP_API_KEY_VALIDATOR
from common.logging.middleware import RequestLoggingMiddleware
from common.logging.exception_handlers import setup_exception_handlers


iterable_tags_metadata = [
    {
        'name': 'Campaign Builder',
        'description': 'The Campaign Builder endpoint used in Iterable as a data feed to populate UTM params an other dynamic campaign fields.',
    }, {
        'name': 'General',
        'description': 'Shared Iterable data feed endpoints.',
    }, {
        'name': 'Mashup Media',
        'description': 'Iterable data feed endpoints specific to Mashup Media content.',
    }, {
        'name': 'Physician\'s Weekly',
        'description': 'Iterable data feed endpoints specific to Physician\'s Weekly content.',
    }, {
        'name': 'Deprecated',
        'description': 'These endpoints have been deprecated and may no longer work. ',
    }
]

iterable_app = FastAPI(openapi_tags=iterable_tags_metadata,
                       swagger_ui_parameters={
                            'docExpansion':'none',
                            'defaultModelsExpandDepth': -1
                        })

iterable_app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)
iterable_app.add_middleware(RequestLoggingMiddleware, service_name='iterable')

# Setup exception handlers
setup_exception_handlers(iterable_app, service_name='iterable')

mashup_service = MashupService()
wordpress_service = WordPressService()
# wordpress_service_bq = WordPressServiceBQ()
sponsored_service = SponsoredContentService()
# sponsored_service_bq = SponsoredContentServiceBQ()
campaign_service = CampaignBuilderService()
wallboard_service = WallboardService()


@iterable_app.get('/mashup/experts/{author}/', tags=['Mashup Media']) #, dependencies=[Depends(ITERABLE_APP_API_KEY_VALIDATOR)])
def read_mashup_expert(author: str):
    return mashup_service.get_expert_articles(author)


@iterable_app.get('/mashup/experts-collection/{collection_slug}/', tags=['Mashup Media']) #, dependencies=[Depends(ITERABLE_APP_API_KEY_VALIDATOR)])
def read_mashup_collection(collection_slug: str):
    return mashup_service.get_collection_articles(collection_slug)


@iterable_app.get('/categories/{site}/', tags=['General']) #, dependencies=[Depends(ITERABLE_APP_API_KEY_VALIDATOR)])
def read_v2_categories(site: AnnotatedSiteParam):
    '''
    Retrieve all available categories for the specified website.
    These categories can then be used in the /v2/iterable_feeds/{site}/{category}/ endpoint.
    '''
    return wordpress_service.get_categories(site)


@iterable_app.get('/content/{site}/{category}/', tags=['General']) #, dependencies=[Depends(ITERABLE_APP_API_KEY_VALIDATOR)])
def read_v2_item(params: GeneralIterableFeedParams = Depends(build_params)):
    '''
    Retrieve the 20 most recent posts for the selected site and filtering options.
    The results are ordered in descending using the publish date.
    Featured items are surfaced to the top of the list and are also orderd in descending order using publish date.
    '''
    # return wordpress_service_bq.get_feed_items(params)
    return wordpress_service.get_feed_items(params)


@iterable_app.get('/sponsored_campaign/{template_name}/', tags=['General']) #, dependencies=[Depends(ITERABLE_APP_API_KEY_VALIDATOR)])
def read_sponsored_item(template_name: str):
    '''
    Retrieve the 20 most recent posts for the selected site and filtering options.
    The results are ordered in descending using the publish date.
    Featured items are surfaced to the top of the list and are also orderd in descending order using publish date.
    '''
    # return sponsored_service_bq.get_sponsored_items(template_name)
    return sponsored_service.get_sponsored_items(template_name)


@iterable_app.get('/campaign_builder/', tags=['Campaign Builder']) #, dependencies=[Depends(ITERABLE_APP_API_KEY_VALIDATOR)])
def get_campaign_builder_feed(campaignName: str):
    '''
    Returns all campaigns from the iterable_campaign_builder table
    whose send_at is today or up to 21 days in the future.
    '''
    return campaign_service.get_campaign_feed(campaignName)


@iterable_app.get('/wallboard/', tags=['Physician\'s Weekly']) #, dependencies=[Depends(ITERABLE_APP_API_KEY_VALIDATOR)])
def get_wallboard_feed(template_name: str = Query(description=wallboard_template_desc)):
    '''
    Returns the metadata for a given category_slug (a.k.a. dpf_zone) in order to populate an Iterable email template.
    '''
    return wallboard_service.get_wallboard_feed(template_name)


# @iterable_app.get('/amc/{site_nm}/', tags=['Deprecated']) #'AMC',
# def read_amc_item(params: AMCParams=Depends()):
#     mongo = AMCMongo()
#     excludeCats = params.exclude.split(',') if params.exclude else None
#     excludeCats = [d.strip() for d in excludeCats] if excludeCats else None
#     articles = mongo.get_articles(params.site_nm,
#                                   params.or_categories,
#                                   params.and_categories,
#                                   params.newer_than_n_days,
#                                   excludeCats,
#                                   params.limit)
#     mongo.__client__.close()

#     return { 'items': articles }
