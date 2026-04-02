from fastapi import APIRouter, Request, HTTPException, Header
import hmac
import hashlib
from datetime import datetime
from pathlib import Path
import json
from google.cloud import storage
from video_upload_service.services.upload_service import UploadService
from video_upload_service.models.upload_session import UploadStatus, UploadSession
from video_upload_service.models.brightcove_callback import BrightcoveCallback
from video_upload_service.core.config import settings
from video_upload_service.workers.ingest_worker import IngestWorker
from video_upload_service.core.metrics import (
    metric_ingest_completed,
    metric_ingest_failed,
    metric_ingest_success_rate,
    ingest_timer_end
)

from video_upload_service.services.cloud_tasks_service import CloudTasksService
from video_upload_service.core.logger import logger

router = APIRouter(prefix="/v1/brightcove", tags=["Brightcove"])

upload_service = UploadService()

@router.post("/callback")
async def brightcove_callback(
    request: Request,
    payload: BrightcoveCallback,
    x_callback_secret: str = Header(...),
    x_signature: str | None = Header(...)
    ):

    # security requirement - callback secret verification
    if x_callback_secret != settings.BRIGHTCOVE_CALLBACK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid callback secret")
    
    if x_signature:
        raw_body = await request.body()

        expected_signature = hmac.new(
            settings.BRIGHTCOVE_CALLBACK_SECRET.encode(),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, x_signature):
            logger.info("CALLBACK_SIGNATURE_MISMATCH detected (placeholder mode)")

    job_id = payload.jobId
    status = payload.status

    if not job_id:
        raise HTTPException(status_code=400, detail="Missing jobId")

    # from pathlib import Path
    # import json

    # base = Path("local_metadata/uploads")
    

    # for session_file in base.glob("*/session.json"):
    #     with open(session_file, "r", encoding="utf-8") as f:
    #         data = json.load(f)

    sessions = []

    # DEV MODE → read local metadata

    if settings.ENV != "prod":

        base = Path("local_metadata/uploads")

        for session_file in base.glob("*/session.json"):
            with open(session_file, "r", encoding="utf-8") as f:
                sessions.append(json.load(f))

    # PROD MODE → read from GCS

    else:

        client = storage.Client()

        blobs = client.list_blobs(
            settings.GCS_STAGING_BUCKET,
            prefix="staging/"
        )

        for blob in blobs:

            if not blob.name.endswith("session.json"):
                continue

            try:
                data = json.loads(blob.download_as_text())
                sessions.append(data)
            except Exception:
                continue
    
    # Finding Matching sessions
    
    for data in sessions:

        brightcove_data = data.get("brightcove", {})
        if (
            brightcove_data.get("job_id") == job_id or payload.videoId == brightcove_data.get("video_id")
        ):

            session_id = data["id"]
            data = upload_service.storage.read_json(
                f"uploads/{session_id}/session.json"
            )

            generation = data.get("_generation")

            session = UploadSession(**data)

            # Idempotent callback handling
            if session.status in [UploadStatus.COMPLETE, UploadStatus.FAILED]:
                logger.info(f"DUPLICATE_CALLBACK_IGNORED session_id={session_id} status={session.status}")
                return {"status": "ignored_duplicate"}

            worker = IngestWorker()
            mapped_status = worker.map_ingest_state(status)

            # if session.status == UploadStatus.COMPLETE:
            #     return {"status": "ignored_duplicate"}
        
            MAX_RETRIES = 3

            if mapped_status == UploadStatus.FAILED:

                retry_count = session.retry_count or 0

                if retry_count < MAX_RETRIES:

                    retry_count += 1
                    session.retry_count = retry_count

                    remaining = MAX_RETRIES - retry_count

                    logger.info(
                        f"INGEST_RETRY_SCHEDULED session_id={session_id} retry={retry_count}"
                    )

                    logger.info(f"INGEST_FAILED session_id={session_id}, retries_left={remaining}")

                    # enqueue again via Cloud Tasks (DEV executes instantly)
                    cloud_tasks = CloudTasksService()
                    cloud_tasks.enqueue_ingest_job(session_id)

                    # keep ingesting state while retrying
                    session.status = UploadStatus.INGESTING

                    message = f"{remaining} retries left, retry again"

                    if remaining == 0:
                        message = "0 retries left. Next failure will mark status as FAILED."

                    response_payload = {
                        "status": "retrying",
                        "retry_attempt": retry_count,
                        "retries_left": remaining,
                        "message": message
                    }

                else:
                    session.status = UploadStatus.FAILED

                    session.error = {
                        "code": "INGEST_MAX_RETRIES_EXCEEDED",
                        "message": "Maximum retry attempts reached"
                    }
                    logger.info(
                        f"INGEST_MAX_RETRIES_EXCEEDED session_id={session_id}"
                    )

                    metric_ingest_failed(session_id)
                    metric_ingest_success_rate(session_id, success=False)
                    ingest_timer_end(session_id)

                    response_payload = {
                        "status": "failed",
                        "message": "Status is FAILED. Use /v1/uploads/{session_id}/retry endpoint to restart ingest."
                    }

            elif mapped_status == UploadStatus.COMPLETE:

                session.status = UploadStatus.COMPLETE
                metric_ingest_completed(session_id)
                metric_ingest_success_rate(session_id, success=True)
                ingest_timer_end(session_id)

                response_payload = {
                    "status": "complete",
                    "message": "Video successfully ingested into Brightcove."
                }

            else:
                session.status = mapped_status

                response_payload = {
                "status": str(mapped_status),
                "message": "Ingest status Updated"
            }

            session.updated_at = datetime.utcnow()

            upload_service.storage.write_json(
                f"uploads/{session_id}/session.json",
                session.model_dump(),
                expected_generation=generation
            )

            upload_service.event_service.write_event(
                session_id,
                "INGEST_CALLBACK",
                payload.model_dump()
            )

            return response_payload

    logger.info(f"ALERT callback_without_session job_id={job_id}")
    return {"status": "session_not_found"}