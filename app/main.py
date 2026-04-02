from fastapi import FastAPI, Request
from starlette.templating import Jinja2Templates
from services import *
from fastapi.middleware.cors import CORSMiddleware
from ai.app import ai_app
from iterable.app import iterable_app
from internal.app import internal_app
# from external.app import external_app

# Video_upload_service_dev-vkp
from video_upload_service.app import video_upload_app
from video_upload_service.app import video_upload_app



app = FastAPI(docs_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)
versions = {
    'ai': 1,
    'internal': 1,
    'iterable': 3,
    'external': 1
}
templates = Jinja2Templates(directory='app/templates')
health_service = HealthService()

@app.get('/health', include_in_schema=False)
def health():
    return health_service.get_health_status()

@app.get('/')
def index(request: Request):
    return templates.TemplateResponse(
        request=request, name='index.html', context=versions
    )


app.mount(f"/ai/v{versions['ai']}", ai_app)
app.mount(f"/internal/v{versions['internal']}", internal_app)
app.mount(f"/iterable/v{versions['iterable']}", iterable_app)
# app.mount(f"/external/v{versions['external']}", external_app)


# Video_upload_service_dev-vkp
app.mount("/video-upload/v1", video_upload_app)
app.mount("/video/v1", video_upload_app)
