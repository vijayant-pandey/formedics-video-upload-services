from fastapi import APIRouter, HTTPException, Depends 
from video_upload_service.core.rbac import require_editor, require_admin
from video_upload_service.core.scopes import require_scope
from ..models.upload_request import CreateUploadRequest
from ..services.upload_service import UploadService
from ..core.security import verify_jwt_token
from video_upload_service.core.config import settings
from google.cloud import storage
from video_upload_service.core.config import settings
import json


router = APIRouter(
    prefix="/v1/uploads", 
    tags=["Uploads"],
    dependencies=[Depends(require_editor)]
)

upload_service = UploadService()


@router.get("/jobs")
def list_uploads():

    client = storage.Client()

    blobs = client.list_blobs(
        settings.GCS_STAGING_BUCKET,
        prefix="staging/"
    )

    uploads = []

    for blob in blobs:

        # Only read the session.json file inside each session folder
        if blob.name.count("/") == 2 and blob.name.endswith("session.json"):

            try:
                data = blob.download_as_text()
                uploads.append(json.loads(data))
            except Exception:
                continue

    return {
        "count": len(uploads),
        "uploads": uploads
    }

@router.post("")
async def create_upload(
    request: CreateUploadRequest,
    user=Depends(verify_jwt_token)
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    require_scope(user, "upload:create")

    result = upload_service.create_upload_session(request)
    return {
        "session_id": result["session"].id,
        "status": result["session"].status,
        "upload_url": result["upload_url"],
        "expires_at": result["expires_at"]
    }


@router.post("/{session_id}/complete")
async def complete_upload(
    session_id: str, 
    user=Depends(verify_jwt_token)
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    require_scope(user, "upload:create")

    session = upload_service.complete_upload(session_id)
    return {
        "session_id": session.id,
        "status": session.status
    }



@router.get("/{session_id}")
async def get_upload(
    session_id: str, 
    user=Depends(verify_jwt_token)
):
    require_scope(user, "upload:read")

    session = upload_service.get_session(session_id)
    return session


@router.post("/{session_id}/retry")
async def retry_upload(
    session_id: str, 
    user=Depends(verify_jwt_token)
):

    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    require_scope(user, "upload:retry")

    session = upload_service.retry_upload(session_id)

    return {
        "id": session.id,
        "status": session.status
    }


# ======================================================================
# Added omn 02/03/2026 to check direct upload by using google python client library to upload to GCS,
#  bypassing the need for signed URLs and allowing for larger file uploads without hitting URL size limits. 
# This is only allowed in PROD mode and requires admin role.

from fastapi import UploadFile, File

@router.put("/{session_id}/direct-upload")
async def direct_upload(
    session_id: str,
    file: UploadFile = File(...),
    user=Depends(verify_jwt_token)
):
    if settings.ENV != "prod":
        raise HTTPException(status_code=400, detail="Direct upload only allowed in PROD mode")

    require_scope(user, "upload:create")

    session = upload_service.get_session(session_id)

    content = await file.read()

    upload_service.storage.upload_to_gcs(
        session.gcs_bucket,
        session.gcs_object_path,
        content,
        session.content_type
    )

    return {
        "status": "uploaded_to_gcs",
        "object_path": session.gcs_object_path
    }

# ======================================================================

@router.post("/{session_id}/refresh")
async def refresh_upload(
    session_id: str,
    user=Depends(verify_jwt_token)
):

    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    require_scope(user, "upload:create")

    result = upload_service.refresh_upload_url(session_id)

    return {
        "session_id": result["session"].id,
        "upload_url": result["upload_url"],
        "expires_at": result["expires_at"]
    }




