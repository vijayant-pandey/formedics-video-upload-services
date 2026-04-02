from fastapi import Depends, FastAPI, Query
from .dtypes import *
from .services import *
from .els_types import JournalName
from fastapi.middleware.cors import CORSMiddleware
from security import AI_APP_API_KEY_VALIDATOR, BACKEND_SERVICES_KEY_VALIDATOR
from common.logging.middleware import RequestLoggingMiddleware
from common.logging.exception_handlers import setup_exception_handlers
from typing import Optional


ai_tags_metadata = [{
        'name': 'General',
        'description': '',
    }
]

ai_app = FastAPI(openapi_tags=ai_tags_metadata,
                 swagger_ui_parameters={
                     'docExpansion':'none',
                     'defaultModelsExpandDepth': -1
                })

ai_app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)
ai_app.add_middleware(RequestLoggingMiddleware, service_name='ai')

# Setup exception handlers
setup_exception_handlers(ai_app, service_name='ai')

gen_subj_service = GenSubjLineService()
gen_els_summary_service = JournaySummaryService()
aga_vector_search_service = AGAVectorSearchService()
ai_content_detection_service = DetectAIContent()

@ai_app.post('/gen_subject_line/', tags=['General'], include_in_schema=True, dependencies=[Depends(AI_APP_API_KEY_VALIDATOR)])
def gen_subject_line(articles:SubjSource):
    '''
    Expects a list of articles and returns AI generated subject lines and preheaders for each article
    '''
    return gen_subj_service.generate(articles.model_dump()['articles'])


@ai_app.post('/gen_elsevier_summaries/', tags=['General'], include_in_schema=True, dependencies=[Depends(BACKEND_SERVICES_KEY_VALIDATOR)])
def gen_elevier_summary(
    journal: JournalName = Query(description="Journal/Publication name to search"),
    additional_queries: Optional[str] = Query(default=None, description="Additional search parameters to filter results (e.g., 'IBD', 'Crohn's disease')"),
    # save_raw_data: bool = Query(default=False, description="Save raw article data to file before summarization"),
    batch_size: int = Query(default=5, ge=1, le=25, description="Number of articles to process per batch (1-25). Lower values reduce token usage but increase API calls."),
    save_failed_to: str = Query(default='gcs', description="Where to save failed batches: 'local' (data/failed_batches), 'gcs' (GCS bucket), 'both', or 'none'"),
    start_date: Optional[str] = Query(default=None, description="Filter articles published on or after this date (format: YYYY-MM-DD)")
):
    '''
    Generates AI summaries for articles from a specified Elsevier journal.
    Optionally accepts additional search query parameters to further filter results.
    https://blog.scopus.com/boolean-searches-in-scopus-understanding-operator-precedence-best-practices/

    The batch_size parameter controls how many articles are processed in a single API call:
    - Lower values (1-3): Safer for large articles, lower token usage per call
    - Medium values (4-7): Balanced approach (recommended)
    - Higher values (8-25): Faster but may hit token limits with long articles

    The save_failed_to parameter controls where failed batch data is saved for retry:
    - 'local': Save to local data/failed_batches directory
    - 'gcs': Save to Google Cloud Storage (aga_summarization bucket)
    - 'both': Save to both local and GCS
    - 'none': Don't save failed batches (not recommended for production)

    The start_date parameter filters articles published on or after the specified date:
    - Format: YYYY-MM-DD (e.g., '2024-01-15')
    - Only articles with publication_date >= start_date will be processed
    '''
    query = f'ISSN({journal.issn})'
    if additional_queries:
        query = f'{query} AND {additional_queries}'

    return gen_els_summary_service.generate(
        query,
        save_to_db=True,
        # save_raw_data=save_raw_data,
        source_journal=str(journal),
        source_issn=journal.issn,
        batch_size=batch_size,
        save_failed_to=save_failed_to,
        start_date=start_date
    )


@ai_app.get('/aga_search/', tags=['General'], include_in_schema=True, dependencies=[Depends(AI_APP_API_KEY_VALIDATOR)])
def aga_search(
    journal:JournalName = Query(description="Journal/Publication name to search"),
    search_query:str = Query(default=None, description="Keywords to look for in the summarized articles.")
):
    '''
    Search for relevant journal article summaries using semantic vector search.

    This endpoint uses AI-powered embeddings to find articles semantically similar to your search query,
    returning the top 50 most relevant results from the specified journal. Results are ranked by
    similarity distance, with lower distances indicating higher relevance.

    Returns article details including headline, authors, summary, key takeaways, methods, results,
    clinical relevance, and metadata (DOI, PII, publication date).
    '''
    return aga_vector_search_service.search(
        journal.issn,
        search_query
    )


@ai_app.post('/detect_ai_content/', tags=['General'], include_in_schema=True, dependencies=[Depends(AI_APP_API_KEY_VALIDATOR)])
def detect_ai(articles:DetectionPosts):
    '''
    Analyzes text content to detect if it was AI-generated using pattern recognition and stylistic analysis.

    This endpoint examines the provided content for patterns, phrases, and stylistic elements commonly
    associated with AI-generated text, including low perplexity, generic language, and common LLM
    disclaimers or patterns. The analysis provides a confidence score (0-100%) indicating the likelihood
    of AI authorship, along with detailed reasoning and sample excerpts supporting the assessment.

    Returns a detailed analysis including:
    - confidence_score: Percentage (0-100%) likelihood of AI-generation
    - explanation: Detailed reasoning referencing specific patterns and stylistic elements
    - samples: Array of sample phrases from the input text that support the analysis
    '''
    return ai_content_detection_service.generate(articles.model_dump())
