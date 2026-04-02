from fastapi import APIRouter, UploadFile, File, HTTPException
from video_upload_service.services.upload_service import UploadService
from video_upload_service.core.config import settings

router = APIRouter(prefix="/dev", tags=["DevTools"])

upload_service = UploadService()


@router.put("/fake-upload/{session_id}")
async def fake_upload(session_id: str, file: UploadFile = File(...)):

    # Only allow in DEV
    if settings.ENV != "dev":
        raise HTTPException(status_code=403, detail="Disabled outside dev just for swagger fake upload testing- dont use if not in dev")

    session = upload_service.get_session(session_id)


    # write file to staging path via storage service
    content = await file.read()

    # write binary using existing storage abstraction
    upload_service.storage.write_binary(
        session.gcs_object_path,
        content
    )

    return {
        "status": "fake_uploaded",
        "object_path": session.gcs_object_path
    }