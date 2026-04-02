# import sys
# import os

# local import fix (safe and only affects video_upload_service)
# BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# if BASE_DIR not in sys.path:
#     sys.path.insert(0, BASE_DIR)
# # ---------------------------------------------------------------


from fastapi import FastAPI, Request
import uuid
from video_upload_service.core.logger import logger
from .api.uploads import router as upload_router
from .api.brightcove import router as brightcove_router
from .api.worker import router as worker_router
from video_upload_service.api.dev_tools import router as dev_roter
from video_upload_service.api.debug import router as debug_router

video_upload_app = FastAPI(
    title="Video Upload Service",
    docs_url="/docs"
)

# correlation id middleware for observability
@video_upload_app.middleware("http")
async def correlation_middleware(request: Request, call_next):

    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

    # attach to request state
    request.state.correlation_id = correlation_id

    try:
        response = await call_next(request)
    except Exception:
        raise

    response.headers["X-Correlation-ID"] = correlation_id

    # safer logging for mounted apps
    logger.info(
        f"REQ correlation_id={correlation_id} method={request.method} path={request.scope.get('path')}"
    )

    return response


video_upload_app.include_router(upload_router)
video_upload_app.include_router(brightcove_router)
video_upload_app.include_router(worker_router)
video_upload_app.include_router(dev_roter)
video_upload_app.include_router(debug_router)

from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

upload_templates = Jinja2Templates(
    directory=os.path.join(BASE_DIR, "templates")
)

@video_upload_app.get("/admin", response_class=HTMLResponse)
async def upload_admin_ui(request: Request):
    return upload_templates.TemplateResponse(
        "index.html",
        {"request": request}
    )