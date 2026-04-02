from fastapi import APIRouter, Header, HTTPException, Request
from video_upload_service.workers.ingest_worker import IngestWorker
from video_upload_service.core.config import settings

router = APIRouter(prefix="/v1/worker", tags=["Worker"])

worker = IngestWorker()

def verify_cloud_run_identity(request: Request):

    # Cloud Run injects Authorization: Bearer <OIDC_TOKEN>
    auth = request.headers.get("Authorization")

    if settings.ENV == "dev":
        return True

    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing OIDC token")

    return True

from pydantic import BaseModel

class WorkerIngestRequest(BaseModel):
    session_id: str

@router.post("/ingest")
async def ingest_worker(body: WorkerIngestRequest, request: Request):

    verify_cloud_run_identity(request)

    session_id = body.session_id

    worker.process(session_id)

    return {
        "status": "worker_executed",
        "session_id": session_id
    }